"""
FastAPI server for PDF translation service
"""

import asyncio
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from dotenv import load_dotenv

import uvicorn
from fastapi import BackgroundTasks
from fastapi import FastAPI
from fastapi import File
from fastapi import Form
from fastapi import HTTPException
from fastapi import UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pdf2zh_next.config import ConfigManager
from pdf2zh_next.config.cli_env_model import CLIEnvSettingsModel
from pdf2zh_next.config.model import SettingsModel
from pdf2zh_next.high_level import TranslationError
from pdf2zh_next.high_level import do_translate_async_stream
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PDFMathTranslate API", description="API for translating PDF files with preserved formatting", version="1.0.0")

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
active_tasks: Dict[str, asyncio.Task] = {}
task_results: Dict[str, dict] = {}


class TranslationRequest(BaseModel):
    # Translation service settings
    service: str = "openai"
    lang_from: str = "English"
    lang_to: str = "Simplified Chinese"

    # Page settings
    page_range: str = "All"
    page_input: Optional[str] = None

    # PDF output options
    no_mono: bool = False
    no_dual: bool = False
    dual_translate_first: bool = False
    use_alternating_pages_dual: bool = False
    watermark_output_mode: str = "Watermarked"

    # Advanced translation options
    prompt: Optional[str] = None
    threads: int = 4
    min_text_length: int = 10
    rpc_doclayout: Optional[str] = None
    custom_system_prompt_input: Optional[str] = None
    pool_max_workers: Optional[int] = None
    no_auto_extract_glossary: bool = False
    primary_font_family: str = "Auto"

    # PDF processing options
    skip_clean: bool = False
    disable_rich_text_translate: bool = False
    enhance_compatibility: bool = False
    split_short_lines: bool = False
    short_line_split_factor: float = 0.5
    translate_table_text: bool = False
    skip_scanned_detection: bool = False
    ocr_workaround: bool = False
    auto_enable_ocr_workaround: bool = False
    max_pages_per_part: int = 0
    formular_font_pattern: Optional[str] = None
    formular_char_pattern: Optional[str] = None
    ignore_cache: bool = False

    # Translation engine specific settings (dynamic)
    engine_settings: Dict[str, Union[str, int, bool]] = {}


class LanguageInfo(BaseModel):
    display_name: str
    code: str


class ServiceInfo(BaseModel):
    name: str
    fields: List[dict]


@app.get("/")
async def read_root():
    """Serve the main frontend page"""
    return FileResponse("static/index.html")


@app.get("/api/languages")
async def get_languages() -> List[LanguageInfo]:
    """Get available languages for translation"""
    from pdf2zh_next.mappings import lang_map

    languages = []
    for display_name, code in lang_map.items():
        languages.append(LanguageInfo(display_name=display_name, code=code))

    return languages


@app.get("/api/services")
async def get_services() -> List[ServiceInfo]:
    """Get available translation services and their configuration fields"""
    import os

    # Define supported models and their configurations
    supported_models = [
        {
            "name": "claude-sonnet-4-20250514",
            "display_name": "Claude Sonnet 4",
            "service_type": "Anthropic",  # Using OpenAI-compatible API
            "env_vars": ["ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"],
        },
        {"name": "gpt-4o-mini", "display_name": "GPT-4o Mini", "service_type": "OpenAI", "env_vars": ["OPENAI_API_KEY", "OPENAI_BASE_URL"]},
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


def _build_settings_from_request(request: TranslationRequest, file_path: Path, output_dir: Path) -> SettingsModel:
    """Build SettingsModel from API request parameters"""
    import os

    from pdf2zh_next.mappings import lang_map
    from pdf2zh_next.mappings import page_map

    # Map selected model to appropriate service
    model_service_map = {
        "claude-sonnet-4-20250514": "Anthropic",  # Claude via OpenAI-compatible API
        "gpt-4o-mini": "OpenAI",
        "claude-3-5-sonnet-20240620": "Anthropic",  # Claude via OpenAI-compatible API
    }

    # Get the appropriate service name
    service_name = model_service_map.get(request.service, "OpenAI")

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
        raise HTTPException(status_code=400, detail=f"Invalid settings: {e}")

    return settings


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
                task_results[task_id].update(
                    {
                        "status": "completed",
                        "progress": 100,
                        "stage": "Translation complete",
                        "result": {
                            "mono_pdf_path": str(result.mono_pdf_path) if result.mono_pdf_path else None,
                            "dual_pdf_path": str(result.dual_pdf_path) if result.dual_pdf_path else None,
                            "total_seconds": result.total_seconds,
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


@app.post("/api/translate")
async def translate_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...), request_data: str = Form(...)):
    """Start PDF translation"""
    try:
        # Parse request data
        import json

        request = TranslationRequest(**json.loads(request_data))

        # Validate file
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Create unique task ID and output directory
        task_id = str(uuid.uuid4())
        output_dir = Path("pdf2zh_files") / task_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save uploaded file
        file_path = output_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Build translation settings
        settings = _build_settings_from_request(request, file_path, output_dir)

        # Start background translation task
        task = asyncio.create_task(_translation_task(task_id, settings, file_path))
        active_tasks[task_id] = task

        return {"task_id": task_id, "status": "started"}

    except Exception as e:
        logger.error(f"Error starting translation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info")

    uvicorn.run("api_server:app", host=host, port=port, reload=reload, log_level=log_level)


if __name__ == "__main__":
    main()
