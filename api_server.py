"""
FastAPI server for PDF translation service
"""

import asyncio
import logging
import shutil
import uuid
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi import File
from fastapi import HTTPException
from fastapi import Request
from fastapi import UploadFile
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pdf2zh_next.config import ConfigManager
from pdf2zh_next.config.cli_env_model import CLIEnvSettingsModel
from pdf2zh_next.config.model import SettingsModel
from pdf2zh_next.high_level import do_translate_async_stream
from pdf2zh_next.storage import upload_to_storage
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PDFMathTranslate API", description="API for translating PDF files with preserved formatting", version="1.0.0")


# Custom exception handler for validation errors to handle binary data
@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
    """Custom handler for validation errors that may contain binary data"""

    # Log detailed information about the validation error
    logger.error(f"Validation error on {request.method} {request.url.path}")
    logger.error(f"Error count: {len(exc.errors())}")

    # Try to log safe error information first
    safe_errors = []
    for i, error in enumerate(exc.errors()):
        safe_error = {
            "type": error.get("type", "unknown"),
            "loc": error.get("loc", []),
            "msg": error.get("msg", "Validation error"),
        }
        safe_errors.append(safe_error)
        logger.error(f"Error {i + 1}: {safe_error}")

    try:
        # Try the default handler first
        return await request_validation_exception_handler(request, exc)
    except UnicodeDecodeError as unicode_error:
        # If we get a unicode decode error, create a safe error response
        logger.error(f"Unicode decode error in validation: {unicode_error}")
        logger.error("Returning safe error response without binary data")

        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=422, content={"detail": safe_errors, "message": "Validation failed. Some request data could not be processed."})
    except Exception as other_error:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error in validation handler: {type(other_error).__name__}: {other_error}")

        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=422, content={"detail": safe_errors, "message": "Validation failed due to an unexpected error."})


# Note: Debug middleware was removed after resolving the request format issue

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files for frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global variables
config_manager = ConfigManager()
try:
    base_settings = config_manager.initialize_cli_config()
except Exception as e:
    logger.warning(f"Could not load initial config: {e}")
    base_settings = CLIEnvSettingsModel()

# Store active translation tasks
active_tasks: dict[str, asyncio.Task] = {}
task_results: dict[str, dict] = {}
uploaded_files: dict[str, Path] = {}  # Store uploaded files by ID

# Module-level dependency to avoid function calls in defaults
FILE_DEPENDENCY = File(...)


class TranslationRequest(BaseModel):
    """
    PDF翻译请求参数模型

    包含所有PDF翻译过程中的配置选项，从基础的翻译服务设置到高级的PDF处理选项。
    """

    # Translation service settings
    service: str = "gpt-4o-mini"
    """翻译服务选择。可选值：gpt-4o-mini, claude-sonnet-4-20250514, claude-3-5-sonnet-20240620"""

    lang_from: str = "English"
    """源语言。支持的语言请参考 /api/languages 接口"""

    lang_to: str = "Simplified Chinese"
    """目标语言。支持的语言请参考 /api/languages 接口"""

    # Page settings
    page_range: str = "All"
    """翻译页面范围。可选值：All(全部页面), First(仅第一页), First 5 pages(前5页), Range(自定义范围)"""

    page_input: str | None = None
    """自定义页面范围，当page_range为Range时使用。格式：1,3,5-10"""

    # PDF output options
    no_mono: bool = False
    """禁用单语输出PDF"""

    no_dual: bool = False
    """禁用双语输出PDF"""

    dual_translate_first: bool = False
    """双语模式中翻译页面在前（默认原文在前）"""

    use_alternating_pages_dual: bool = False
    """双语PDF使用交替页面模式"""

    watermark_output_mode: str = "Watermarked"
    """水印模式。可选值：Watermarked(带水印), No Watermark(无水印)"""

    # Advanced translation options
    prompt: str | None = None
    """自定义翻译提示词（已废弃，请使用custom_system_prompt_input）"""

    threads: int = Field(default=4, ge=1, le=20)
    """每秒请求数（QPS），控制翻译速度，范围：1-20"""

    min_text_length: int = Field(default=10, ge=0)
    """最小翻译文本长度，小于此长度的文本将不被翻译"""

    rpc_doclayout: str | None = None
    """文档布局分析RPC服务地址（可选）"""

    custom_system_prompt_input: str | None = None
    """自定义系统提示，用于调整翻译风格和行为。例如：/no_think 你是一个专业、地道的机器翻译引擎。"""

    pool_max_workers: int | None = None
    """线程池最大工作线程数，为None时使用默认值"""

    no_auto_extract_glossary: bool = False
    """禁用自动术语提取"""

    primary_font_family: str = "Auto"
    """主要字体系列。可选值：Auto(自动), serif(衬线字体), sans-serif(无衬线字体), script(手写字体)"""

    # PDF processing options
    skip_clean: bool = False
    """跳过清理步骤（提高兼容性，但可能影响翻译质量）"""

    disable_rich_text_translate: bool = False
    """禁用富文本翻译，仅翻译纯文本内容"""

    enhance_compatibility: bool = False
    """增强兼容性模式，用于处理复杂的PDF格式"""

    split_short_lines: bool = False
    """强制分割短行，有助于提高某些文档的翻译效果"""

    short_line_split_factor: float = Field(default=0.5, ge=0.1, le=1.0)
    """分割阈值因子，控制短行分割的敏感度，范围：0.1-1.0"""

    translate_table_text: bool = False
    """翻译表格文本（实验性功能）"""

    skip_scanned_detection: bool = False
    """跳过扫描文档检测"""

    ocr_workaround: bool = False
    """启用OCR解决方案（实验性功能，用于处理扫描文档）"""

    auto_enable_ocr_workaround: bool = False
    """自动启用OCR解决方案，当检测到扫描文档时"""

    max_pages_per_part: int = Field(default=0, ge=0)
    """每部分最大页数，0表示无限制。用于分批处理大文档"""

    formular_font_pattern: str | None = None
    """公式字体模式匹配（正则表达式）"""

    formular_char_pattern: str | None = None
    """公式字符模式匹配（正则表达式）"""

    ignore_cache: bool = False
    """忽略翻译缓存，强制重新翻译"""

    # Translation engine specific settings (dynamic)
    engine_settings: dict[str, str | int | bool] = {}
    """翻译引擎特定设置，动态配置各翻译服务的专有参数"""

    @field_validator("rpc_doclayout", "custom_system_prompt_input", "formular_font_pattern", "formular_char_pattern", "page_input", mode="before")
    @classmethod
    def validate_optional_strings(cls, v):
        """Convert empty strings to None for optional string fields"""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("pool_max_workers", mode="before")
    @classmethod
    def validate_pool_max_workers(cls, v):
        """Convert 0 to None for pool_max_workers"""
        if v == 0:
            return None
        return v


class LanguageInfo(BaseModel):
    display_name: str
    code: str


class ServiceInfo(BaseModel):
    name: str
    fields: list[dict]


class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    size: int
    message: str


class TranslateWithFileIdRequest(BaseModel):
    """
    使用文件ID启动翻译的请求模型

    先通过 /api/files/upload 上传文件获取 file_id，然后使用此模型启动翻译。
    """

    file_id: str
    """文件ID，通过 /api/files/upload 接口获取"""

    config: TranslationRequest
    """翻译配置参数"""


@app.get("/")
async def read_root():
    """Serve the main frontend page"""
    return FileResponse("static/index.html")


@app.get("/api/languages")
async def get_languages() -> list[LanguageInfo]:
    """Get available languages for translation"""
    from pdf2zh_next.mappings import lang_map

    languages = []
    for display_name, code in lang_map.items():
        languages.append(LanguageInfo(display_name=display_name, code=code))

    return languages


@app.get("/api/services")
async def get_services() -> list[ServiceInfo]:
    """Get available translation services and their configuration fields"""
    import os

    # Define supported models and their configurations
    supported_models = [
        {
            "name": "gpt-4o-mini",
            "display_name": "GPT-4o Mini",
            "service_type": "OpenAI",
            "env_vars": ["OPENAI_API_KEY", "OPENAI_BASE_URL"],
        },
        {
            "name": "claude-sonnet-4-20250514",
            "display_name": "Claude Sonnet 4",
            "service_type": "Anthropic",  # Using OpenAI-compatible API
            "env_vars": ["ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"],
        },
        {
            "name": "claude-3-5-sonnet-20240620",
            "display_name": "Claude 3.5 Sonnet",
            "service_type": "Anthropic",  # Using OpenAI-compatible API
            "env_vars": ["ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"],
        },
    ]

    services = []

    for model in supported_models:
        # Check if required environment variables are set
        env_status = {}
        for env_var in model["env_vars"]:
            env_status[env_var] = bool(os.getenv(env_var))

        service_info = ServiceInfo(
            name=model["name"],
            fields=[
                {
                    "name": "model_name",
                    "description": f"模型名称 ({model['display_name']})",
                    "type": "str",
                    "default": model["name"],
                    "required": True,
                    "is_password": False,
                    "readonly": True,
                },
                {
                    "name": "env_status",
                    "description": "环境变量状态",
                    "type": "dict",
                    "default": env_status,
                    "required": False,
                    "is_password": False,
                    "readonly": True,
                },
            ],
        )
        services.append(service_info)

    return services


@app.post("/api/files/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = FILE_DEPENDENCY):
    """
    上传PDF文件

    接受PDF文件上传，返回文件ID供后续翻译使用。

    参数：
    - file: PDF文件（二进制格式）

    返回：
    - file_id: 文件唯一标识符
    - filename: 原始文件名
    - size: 文件大小（字节）
    - message: 上传状态消息

    注意：上传的文件会临时存储，建议在翻译完成后调用清理接口。
    """
    try:
        # Validate file presence and name
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided or filename is missing")

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Check file size (limit to 100MB)
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        if len(content) > 100 * 1024 * 1024:  # 100MB limit
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 100MB")

        # Basic PDF file validation - check PDF magic number
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Invalid PDF file format")

        # Generate unique file ID
        file_id = str(uuid.uuid4())

        # Create directory for uploaded file
        upload_dir = Path("pdf2zh_files") / "uploads" / file_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Save uploaded file (we already have the content)
        file_path = upload_dir / file.filename
        with file_path.open("wb") as buffer:
            buffer.write(content)

        # Store file info
        uploaded_files[file_id] = file_path

        # Get file size
        file_size = len(content)

        logger.info(f"File uploaded: {file_id} -> {file.filename} ({file_size} bytes)")

        return FileUploadResponse(file_id=file_id, filename=file.filename, size=file_size, message="File uploaded successfully")

    except HTTPException:
        # Re-raise HTTP exceptions to preserve their status codes
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}") from e


@app.post("/api/translate")
async def translate_with_file_id(request: TranslateWithFileIdRequest):
    """
    启动PDF翻译任务

    使用已上传的文件ID和结构化配置参数启动翻译任务。
    此接口提供完整的类型安全性和参数验证。

    参数：
    - file_id: 通过 /api/files/upload 获取的文件ID
    - config: 翻译配置参数（TranslationRequest结构）

    返回：
    - task_id: 翻译任务ID
    - status: 任务状态（started）

    工作流程：
    1. 调用 POST /api/files/upload 上传PDF文件，获取 file_id
    2. 调用 POST /api/translate 传入 file_id 和配置参数启动翻译
    3. 使用 GET /api/task/{task_id}/status 查询翻译进度
    4. 使用 GET /api/task/{task_id}/download/{file_type} 下载结果
    5. 可选：使用 DELETE /api/files/{file_id} 清理上传的文件
    """
    try:
        # Validate file ID
        if request.file_id not in uploaded_files:
            raise HTTPException(status_code=404, detail="File not found. Please upload the file first.")

        file_path = uploaded_files[request.file_id]
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File no longer exists on server")

        # Create unique task ID and output directory
        task_id = str(uuid.uuid4())
        output_dir = Path("pdf2zh_files") / task_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build translation settings
        settings = _build_settings_from_request(request.config, file_path, output_dir)

        # Start background translation task
        task = asyncio.create_task(_translation_task(task_id, settings, file_path))
        active_tasks[task_id] = task

        logger.info(f"Translation started with file_id {request.file_id}, task_id: {task_id}")

        return {"task_id": task_id, "status": "started"}

    except HTTPException:
        # Re-raise HTTP exceptions to preserve their status codes
        raise
    except Exception as e:
        logger.error(f"Error starting translation with file_id: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


def _build_settings_from_request(request: TranslationRequest, file_path: Path, output_dir: Path) -> SettingsModel:
    """Build SettingsModel from API request parameters"""
    import os

    from pdf2zh_next.mappings import lang_map
    from pdf2zh_next.mappings import page_map

    # Note: Model service mapping is handled in the conditional logic below

    # Build settings manually instead of using GUI logic
    settings = base_settings.clone()

    # Map UI language selections to language codes
    source_lang = lang_map.get(request.lang_from, "auto")
    target_lang = lang_map.get(request.lang_to, "zh")

    # Set up page selection
    if request.page_range == "Range" and request.page_input:
        pages = request.page_input
    else:
        selected_pages = page_map.get(request.page_range)
        if selected_pages is None:
            pages = None  # All pages
        else:
            pages = ",".join(str(p + 1) for p in selected_pages)

    # Update basic settings
    settings.basic.input_files = {str(file_path)}
    settings.report_interval = 0.2
    settings.translation.lang_in = source_lang
    settings.translation.lang_out = target_lang
    settings.translation.output = str(output_dir)
    settings.translation.qps = int(request.threads)
    settings.translation.ignore_cache = request.ignore_cache

    # Configure model-specific settings
    if request.service == "claude-sonnet-4-20250514":
        # Configure Claude Sonnet 4 via OpenAI-compatible API
        settings.openai = True
        settings.azure = False
        settings.openai_detail.openai_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        settings.openai_detail.openai_base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        settings.openai_detail.openai_model = "claude-sonnet-4-20250514"

    elif request.service == "gpt-4o-mini":
        # Configure OpenAI settings
        settings.openai = True
        settings.azure = False
        settings.openai_detail.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        settings.openai_detail.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        settings.openai_detail.openai_model = "gpt-4o-mini"

    elif request.service == "claude-3-5-sonnet-20240620":
        # Configure Claude via OpenAI-compatible API
        settings.openai = True
        settings.azure = False
        settings.openai_detail.openai_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        settings.openai_detail.openai_base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        settings.openai_detail.openai_model = "claude-3-5-sonnet-20240620"

    # Disable all other translation engines
    settings.bing = False
    settings.google = False
    settings.deepl = False
    settings.azure = False

    # Apply other settings
    if request.min_text_length is not None:
        settings.translation.min_text_length = int(request.min_text_length)
    if request.rpc_doclayout:
        settings.translation.rpc_doclayout = request.rpc_doclayout
    if request.pool_max_workers is not None and request.pool_max_workers > 0:
        settings.translation.pool_max_workers = int(request.pool_max_workers)
    else:
        settings.translation.pool_max_workers = None
    settings.translation.no_auto_extract_glossary = request.no_auto_extract_glossary
    if request.primary_font_family:
        if request.primary_font_family == "Auto":
            settings.translation.primary_font_family = None
        else:
            settings.translation.primary_font_family = request.primary_font_family

    # Update PDF Settings
    settings.pdf.pages = pages
    settings.pdf.no_mono = request.no_mono
    settings.pdf.no_dual = request.no_dual
    settings.pdf.dual_translate_first = request.dual_translate_first
    settings.pdf.use_alternating_pages_dual = request.use_alternating_pages_dual

    # Map watermark mode
    if request.watermark_output_mode == "Watermarked":
        from pdf2zh_next.config.model import WatermarkOutputMode

        settings.pdf.watermark_output_mode = WatermarkOutputMode.Watermarked
    elif request.watermark_output_mode == "No Watermark":
        from pdf2zh_next.config.model import WatermarkOutputMode

        settings.pdf.watermark_output_mode = WatermarkOutputMode.NoWatermark

    # Update Advanced PDF Settings
    settings.pdf.skip_clean = request.skip_clean
    settings.pdf.disable_rich_text_translate = request.disable_rich_text_translate
    settings.pdf.enhance_compatibility = request.enhance_compatibility
    settings.pdf.split_short_lines = request.split_short_lines
    settings.pdf.ocr_workaround = request.ocr_workaround
    if request.short_line_split_factor is not None:
        settings.pdf.short_line_split_factor = float(request.short_line_split_factor)
    settings.pdf.translate_table_text = request.translate_table_text
    settings.pdf.skip_scanned_detection = request.skip_scanned_detection
    settings.pdf.auto_enable_ocr_workaround = request.auto_enable_ocr_workaround
    if request.max_pages_per_part is not None and request.max_pages_per_part > 0:
        settings.pdf.max_pages_per_part = int(request.max_pages_per_part)
    if request.formular_font_pattern:
        settings.pdf.formular_font_pattern = request.formular_font_pattern
    if request.formular_char_pattern:
        settings.pdf.formular_char_pattern = request.formular_char_pattern

    # Add custom system prompt if provided
    if request.custom_system_prompt_input:
        settings.translation.custom_system_prompt = request.custom_system_prompt_input
    else:
        settings.translation.custom_system_prompt = None

    # Validate settings before proceeding
    try:
        settings.validate_settings()
        return settings.to_settings_model()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid settings: {e}") from e


async def _translation_task(task_id: str, settings: SettingsModel, file_path: Path):
    """Background task for translation"""
    try:
        logger.info(f"Starting translation task {task_id}")
        task_results[task_id] = {"status": "running", "progress": 0, "stage": "Initializing", "error": None, "result": None}

        async for event in do_translate_async_stream(settings, file_path):
            if event["type"] in ("progress_start", "progress_update", "progress_end"):
                task_results[task_id].update(
                    {
                        "progress": event["overall_progress"],
                        "stage": event["stage"],
                        "part_index": event.get("part_index", 1),
                        "total_parts": event.get("total_parts", 1),
                        "stage_current": event.get("stage_current", 1),
                        "stage_total": event.get("stage_total", 1),
                    }
                )
            elif event["type"] == "finish":
                result = event["translate_result"]

                # Upload files to object storage
                storage_results = {}
                try:
                    # Upload mono PDF if exists
                    if result.mono_pdf_path and Path(result.mono_pdf_path).exists():
                        logger.info(f"Uploading mono PDF to object storage: {result.mono_pdf_path}")
                        mono_storage = await upload_to_storage(Path(result.mono_pdf_path))
                        if mono_storage:
                            storage_results["mono"] = {
                                "access_url": mono_storage["access_url"],
                                "file_hash": mono_storage["file_hash"],
                                "storage_key": mono_storage["storage_key"],
                            }

                    # Upload dual PDF if exists
                    if result.dual_pdf_path and Path(result.dual_pdf_path).exists():
                        logger.info(f"Uploading dual PDF to object storage: {result.dual_pdf_path}")
                        dual_storage = await upload_to_storage(Path(result.dual_pdf_path))
                        if dual_storage:
                            storage_results["dual"] = {
                                "access_url": dual_storage["access_url"],
                                "file_hash": dual_storage["file_hash"],
                                "storage_key": dual_storage["storage_key"],
                            }
                except Exception as e:
                    logger.error(f"Failed to upload files to storage: {e}")
                    # Continue even if upload fails, local files are still available

                task_results[task_id].update(
                    {
                        "status": "completed",
                        "progress": 100,
                        "stage": "Translation complete",
                        "result": {
                            "mono_pdf_path": str(result.mono_pdf_path) if result.mono_pdf_path else None,
                            "dual_pdf_path": str(result.dual_pdf_path) if result.dual_pdf_path else None,
                            "total_seconds": result.total_seconds,
                            "storage": storage_results,  # Add storage results
                        },
                    }
                )
                break
            elif event["type"] == "error":
                error_msg = event.get("error", "Unknown error")
                task_results[task_id].update({"status": "error", "error": error_msg})
                break

        logger.info(f"Translation task {task_id} completed")

    except asyncio.CancelledError:
        logger.info(f"Translation task {task_id} was cancelled")
        task_results[task_id].update({"status": "cancelled", "error": "Translation was cancelled"})
    except Exception as e:
        logger.error(f"Translation task {task_id} failed: {e}")
        task_results[task_id].update({"status": "error", "error": str(e)})
    finally:
        # Clean up the task from active tasks
        if task_id in active_tasks:
            del active_tasks[task_id]


@app.get("/api/task/{task_id}/status")
async def get_task_status(task_id: str):
    """Get translation task status"""
    if task_id not in task_results:
        raise HTTPException(status_code=404, detail="Task not found")

    return task_results[task_id]


@app.post("/api/task/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running translation task"""
    if task_id in active_tasks:
        active_tasks[task_id].cancel()
        return {"status": "cancelled"}

    if task_id in task_results:
        if task_results[task_id]["status"] == "running":
            task_results[task_id]["status"] = "cancelled"
        return {"status": "cancelled"}

    raise HTTPException(status_code=404, detail="Task not found")


@app.get("/api/task/{task_id}/download/{file_type}")
async def download_result(task_id: str, file_type: str):
    """Download translation result"""
    if task_id not in task_results:
        raise HTTPException(status_code=404, detail="Task not found")

    result = task_results[task_id]
    if result["status"] != "completed" or not result["result"]:
        raise HTTPException(status_code=400, detail="Translation not completed")

    if file_type == "mono":
        file_path = result["result"]["mono_pdf_path"]
    elif file_type == "dual":
        file_path = result["result"]["dual_pdf_path"]
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")

    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="File not found")

    filename = f"translated_{file_type}_{task_id}.pdf"
    return FileResponse(file_path, filename=filename, media_type="application/pdf")


@app.delete("/api/task/{task_id}")
async def cleanup_task(task_id: str):
    """Clean up task files and data"""
    # Cancel if still running
    if task_id in active_tasks:
        active_tasks[task_id].cancel()
        del active_tasks[task_id]

    # Remove task result
    if task_id in task_results:
        del task_results[task_id]

    # Clean up files
    output_dir = Path("pdf2zh_files") / task_id
    if output_dir.exists():
        shutil.rmtree(output_dir)

    return {"status": "cleaned"}


@app.delete("/api/files/{file_id}")
async def cleanup_uploaded_file(file_id: str):
    """
    清理上传的文件

    删除通过 /api/files/upload 上传的文件，释放服务器存储空间。

    参数：
    - file_id: 文件ID

    返回：
    - status: 清理状态
    - message: 操作结果消息
    """
    try:
        if file_id not in uploaded_files:
            raise HTTPException(status_code=404, detail="File not found")

        file_path = uploaded_files[file_id]

        # Remove file and directory
        if file_path.exists():
            # Remove the entire upload directory for this file
            upload_dir = file_path.parent
            shutil.rmtree(upload_dir)

        # Remove from memory
        del uploaded_files[file_id]

        logger.info(f"Cleaned up uploaded file: {file_id}")

        return {"status": "cleaned", "message": f"File {file_id} has been deleted"}

    except HTTPException:
        # Re-raise HTTP exceptions to preserve their status codes
        raise
    except Exception as e:
        logger.error(f"Error cleaning up file {file_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "active_tasks": len(active_tasks), "completed_tasks": len([r for r in task_results.values() if r["status"] == "completed"])}


def main():
    """Main entry point for the API server"""
    import os

    # Load environment variables from .env.local file first, then from system environment
    load_dotenv(".env.local")

    # Create static directory if it doesn't exist
    static_dir = Path("static")
    static_dir.mkdir(exist_ok=True)

    # Create uploads directory
    uploads_dir = Path("pdf2zh_files")
    uploads_dir.mkdir(exist_ok=True)

    # Get configuration from environment variables
    host = os.getenv("HOST", "127.0.0.1")  # Changed from 0.0.0.0 to localhost for security
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info")

    uvicorn.run("api_server:app", host=host, port=port, reload=reload, log_level=log_level)


if __name__ == "__main__":
    main()
