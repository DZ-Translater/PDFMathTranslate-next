"""
FastAPI server for PDF translation service
"""

import asyncio
import logging
import os
import shutil
import uuid
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from pdf2zh_next.config import ConfigManager
from pdf2zh_next.config.cli_env_model import CLIEnvSettingsModel
from pdf2zh_next.config.model import SettingsModel
from pdf2zh_next.high_level import do_translate_async_stream
from pdf2zh_next.storage import upload_to_storage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PDFMathTranslate API",
    description="API for translating PDF files with preserved formatting",
    version="1.0.0"
)


@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
    """Custom handler for validation errors that may contain binary data"""
    logger.error(f"Validation error on {request.method} {request.url.path}")
    
    safe_errors = []
    for error in exc.errors():
        safe_error = {
            "type": error.get("type", "unknown"),
            "loc": error.get("loc", []),
            "msg": error.get("msg", "Validation error"),
        }
        safe_errors.append(safe_error)

    try:
        return await request_validation_exception_handler(request, exc)
    except UnicodeDecodeError:
        return JSONResponse(
            status_code=422,
            content={"detail": safe_errors, "message": "Validation failed."}
        )
    except Exception:
        return JSONResponse(
            status_code=422,
            content={"detail": safe_errors, "message": "Validation failed."}
        )


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
uploaded_files: dict[str, Path] = {}

# Module-level dependency
FILE_DEPENDENCY = File(...)


class TranslationRequest(BaseModel):
    """Translation configuration parameters"""
    lang_from: str = Field(default="English", description="Source language")
    lang_to: str = Field(default="Simplified Chinese", description="Target language")
    service: str = Field(default="SiliconFlowFree", description="Translation service")
    page_range: str = Field(default="All", description="Page range to translate")
    page_input: str | None = Field(default=None, description="Custom page range")
    
    # PDF Output Options
    no_mono: bool = Field(default=False, description="Disable mono output")
    no_dual: bool = Field(default=False, description="Disable dual output")
    dual_translate_first: bool = Field(default=False)
    use_alternating_pages_dual: bool = Field(default=False)
    watermark_output_mode: str = Field(default="Watermarked")
    
    # Rate Limit Options
    qps: int = Field(default=4, description="Queries per second")
    pool_max_workers: int | None = Field(default=None)
    
    # Advanced Options
    min_text_length: int = Field(default=5)
    skip_clean: bool = Field(default=False)
    disable_rich_text_translate: bool = Field(default=False)
    enhance_compatibility: bool = Field(default=False)
    split_short_lines: bool = Field(default=False)
    short_line_split_factor: float = Field(default=0.8)
    translate_table_text: bool = Field(default=True)
    skip_scanned_detection: bool = Field(default=False)
    ocr_workaround: bool = Field(default=False)
    max_pages_per_part: int | None = Field(default=None)
    formular_font_pattern: str | None = Field(default=None)
    formular_char_pattern: str | None = Field(default=None)
    custom_system_prompt_input: str | None = Field(default=None)

    @field_validator("lang_from", "lang_to", "service", mode="before")
    @classmethod
    def strip_strings(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


class TranslateWithFileIdRequest(BaseModel):
    """Request model for translation with file ID"""
    file_id: str = Field(..., description="Uploaded file ID")
    config: TranslationRequest = Field(default_factory=TranslationRequest)


class FileUploadResponse(BaseModel):
    """Response model for file upload"""
    file_id: str
    filename: str
    size: int
    message: str


@app.post("/api/files/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = FILE_DEPENDENCY):
    """Upload a PDF file for translation"""
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        if len(content) > 100 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Max 100MB")

        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Invalid PDF file format")

        file_id = str(uuid.uuid4())
        upload_dir = Path("pdf2zh_files") / "uploads" / file_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / file.filename
        with open(file_path, "wb") as f:
            f.write(content)

        uploaded_files[file_id] = file_path
        file_size = len(content)

        logger.info(f"File uploaded: {file_id} -> {file.filename} ({file_size} bytes)")

        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            size=file_size,
            message="File uploaded successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/translate")
async def translate_with_file_id(request: TranslateWithFileIdRequest):
    """Start PDF translation task with uploaded file ID"""
    try:
        if request.file_id not in uploaded_files:
            raise HTTPException(status_code=404, detail="File not found")

        file_path = uploaded_files[request.file_id]
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File no longer exists")

        task_id = str(uuid.uuid4())
        output_dir = Path("pdf2zh_files") / task_id
        output_dir.mkdir(parents=True, exist_ok=True)

        settings = _build_settings_from_request(request.config, file_path, output_dir)

        task = asyncio.create_task(_translation_task(task_id, settings, file_path))
        active_tasks[task_id] = task

        logger.info(f"Translation started: file_id={request.file_id}, task_id={task_id}")

        return {"task_id": task_id, "status": "started"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting translation: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


def _build_settings_from_request(
    request: TranslationRequest, file_path: Path, output_dir: Path
) -> SettingsModel:
    """Build SettingsModel from API request parameters"""
    from pdf2zh_next.mappings import lang_map, page_map
    from pdf2zh_next.config.translate_engine_model import TRANSLATION_ENGINE_METADATA_MAP

    settings = base_settings.clone()

    # Map language names to codes
    source_lang = lang_map.get(request.lang_from, "en")
    target_lang = lang_map.get(request.lang_to, "zh-CN")

    # Handle page range
    if request.page_range == "Range" and request.page_input:
        pages = request.page_input
    else:
        selected_pages = page_map.get(request.page_range)
        if selected_pages is None:
            pages = None
        else:
            pages = ",".join(str(p + 1) for p in selected_pages)

    # Update basic settings
    settings.basic.input_files = {str(file_path)}
    settings.report_interval = 0.2
    settings.translation.lang_in = source_lang
    settings.translation.lang_out = target_lang
    settings.translation.output = str(output_dir)

    # Update rate limit settings
    settings.translation.qps = request.qps
    if request.pool_max_workers:
        settings.translation.pool_max_workers = request.pool_max_workers

    # Update PDF settings
    settings.pdf.pages = pages
    settings.pdf.no_mono = request.no_mono
    settings.pdf.no_dual = request.no_dual
    settings.pdf.dual_translate_first = request.dual_translate_first
    settings.pdf.use_alternating_pages_dual = request.use_alternating_pages_dual
    settings.pdf.watermark_output_mode = request.watermark_output_mode.lower().replace(" ", "_")

    # Update advanced settings
    settings.translation.min_text_length = request.min_text_length
    settings.pdf.skip_clean = request.skip_clean
    settings.pdf.disable_rich_text_translate = request.disable_rich_text_translate
    settings.pdf.enhance_compatibility = request.enhance_compatibility
    settings.pdf.split_short_lines = request.split_short_lines
    settings.pdf.short_line_split_factor = request.short_line_split_factor
    settings.pdf.translate_table_text = request.translate_table_text
    settings.pdf.skip_scanned_detection = request.skip_scanned_detection
    settings.pdf.ocr_workaround = request.ocr_workaround

    if request.max_pages_per_part:
        settings.pdf.max_pages_per_part = request.max_pages_per_part
    if request.formular_font_pattern:
        settings.pdf.formular_font_pattern = request.formular_font_pattern
    if request.formular_char_pattern:
        settings.pdf.formular_char_pattern = request.formular_char_pattern
    if request.custom_system_prompt_input:
        settings.translation.custom_system_prompt = request.custom_system_prompt_input

    # Configure translation service
    service = request.service
    if service in TRANSLATION_ENGINE_METADATA_MAP:
        from pdf2zh_next.config.translate_engine_model import TRANSLATION_ENGINE_METADATA
        for metadata in TRANSLATION_ENGINE_METADATA:
            setattr(settings, metadata.cli_flag_name, False)
        
        metadata = TRANSLATION_ENGINE_METADATA_MAP[service]
        setattr(settings, metadata.cli_flag_name, True)

    try:
        settings.validate_settings()
        return settings.to_settings_model()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid settings: {e}") from e


async def _translation_task(task_id: str, settings: SettingsModel, file_path: Path):
    """Background task for translation"""
    try:
        logger.info(f"Starting translation task {task_id}")
        task_results[task_id] = {
            "status": "running",
            "progress": 0,
            "stage": "Initializing",
            "error": None,
            "result": None
        }

        async for event in do_translate_async_stream(settings, file_path):
            if event["type"] in ("progress_start", "progress_update", "progress_end"):
                task_results[task_id].update({
                    "progress": event["overall_progress"],
                    "stage": event["stage"],
                    "part_index": event.get("part_index", 1),
                    "total_parts": event.get("total_parts", 1),
                })
            elif event["type"] == "finish":
                result = event["translate_result"]
                storage_results = {}

                try:
                    if result.mono_pdf_path and Path(result.mono_pdf_path).exists():
                        mono_storage = await upload_to_storage(Path(result.mono_pdf_path))
                        if mono_storage:
                            storage_results["mono"] = mono_storage

                    if result.dual_pdf_path and Path(result.dual_pdf_path).exists():
                        dual_storage = await upload_to_storage(Path(result.dual_pdf_path))
                        if dual_storage:
                            storage_results["dual"] = dual_storage
                except Exception as e:
                    logger.error(f"Failed to upload to storage: {e}")

                task_results[task_id].update({
                    "status": "completed",
                    "progress": 100,
                    "stage": "Translation complete",
                    "result": {
                        "mono_pdf_path": str(result.mono_pdf_path) if result.mono_pdf_path else None,
                        "dual_pdf_path": str(result.dual_pdf_path) if result.dual_pdf_path else None,
                        "total_seconds": result.total_seconds,
                        "storage": storage_results,
                    },
                })
                break
            elif event["type"] == "error":
                task_results[task_id].update({
                    "status": "error",
                    "error": event.get("error", "Unknown error")
                })
                break

        logger.info(f"Translation task {task_id} completed")

    except asyncio.CancelledError:
        logger.info(f"Translation task {task_id} cancelled")
        task_results[task_id].update({"status": "cancelled", "error": "Cancelled"})
    except Exception as e:
        logger.error(f"Translation task {task_id} failed: {e}")
        task_results[task_id].update({"status": "error", "error": str(e)})
    finally:
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
    """Download translation result (mono or dual)"""
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
    if task_id in active_tasks:
        active_tasks[task_id].cancel()
        del active_tasks[task_id]

    if task_id in task_results:
        result = task_results[task_id].get("result")
        if result:
            for key in ["mono_pdf_path", "dual_pdf_path"]:
                path = result.get(key)
                if path and Path(path).exists():
                    try:
                        Path(path).unlink()
                    except Exception:
                        pass
        del task_results[task_id]

    task_dir = Path("pdf2zh_files") / task_id
    if task_dir.exists():
        shutil.rmtree(task_dir)

    return {"status": "cleaned"}


@app.delete("/api/files/{file_id}")
async def cleanup_file(file_id: str):
    """Clean up uploaded file"""
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = uploaded_files[file_id]
    if file_path.exists():
        upload_dir = file_path.parent
        shutil.rmtree(upload_dir)

    del uploaded_files[file_id]
    logger.info(f"Cleaned up uploaded file: {file_id}")

    return {"status": "cleaned", "message": f"File {file_id} deleted"}


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_tasks": len(active_tasks),
        "completed_tasks": len([r for r in task_results.values() if r["status"] == "completed"])
    }


def main():
    """Main entry point for the API server"""
    load_dotenv(".env.local")

    Path("pdf2zh_files").mkdir(exist_ok=True)

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info")

    uvicorn.run("api_server:app", host=host, port=port, reload=reload, log_level=log_level)


if __name__ == "__main__":
    main()
