#!/usr/bin/env python3
"""
PDFMathTranslate API Workflow Test Script

This script tests the complete API workflow for PDF translation:
1. Upload PDF file
2. Start translation with configuration
3. Poll for translation progress
4. Download translated files
5. Clean up (optional)

Usage:
    python test_api_workflow.py [--pdf path/to/test.pdf] [--api-url http://localhost:8000]
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Optional

import requests
from requests.exceptions import RequestException

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PDFTranslateAPITester:
    """Test client for PDFMathTranslate API"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.file_id: Optional[str] = None
        self.task_id: Optional[str] = None

    def test_health_check(self) -> bool:
        """Test the health check endpoint"""
        try:
            logger.info("Testing health check endpoint...")
            response = self.session.get(f"{self.base_url}/api/health")
            response.raise_for_status()
            data = response.json()
            logger.info(f"✅ Health check passed: {data}")
            return True
        except RequestException as e:
            logger.error(f"❌ Health check failed: {e}")
            return False

    def test_get_languages(self) -> bool:
        """Test getting available languages"""
        try:
            logger.info("Testing get languages endpoint...")
            response = self.session.get(f"{self.base_url}/api/languages")
            response.raise_for_status()
            languages = response.json()
            logger.info(f"✅ Available languages: {len(languages)} languages")
            for lang in languages[:5]:  # Show first 5
                logger.info(f"  - {lang['display_name']} ({lang['code']})")
            if len(languages) > 5:
                logger.info(f"  ... and {len(languages) - 5} more")
            return True
        except RequestException as e:
            logger.error(f"❌ Get languages failed: {e}")
            return False

    def test_get_services(self) -> bool:
        """Test getting available translation services"""
        try:
            logger.info("Testing get services endpoint...")
            response = self.session.get(f"{self.base_url}/api/services")
            response.raise_for_status()
            services = response.json()
            logger.info(f"✅ Available services: {len(services)} services")
            for service in services:
                logger.info(f"  - {service['name']}")
            return True
        except RequestException as e:
            logger.error(f"❌ Get services failed: {e}")
            return False

    def test_upload_file(self, pdf_path: Path) -> bool:
        """Test uploading a PDF file"""
        try:
            logger.info(f"Testing file upload with: {pdf_path}")

            with open(pdf_path, "rb") as f:
                files = {"file": (pdf_path.name, f, "application/pdf")}
                response = self.session.post(f"{self.base_url}/api/files/upload", files=files)

            response.raise_for_status()
            data = response.json()
            self.file_id = data["file_id"]

            logger.info(f"✅ File uploaded successfully:")
            logger.info(f"  - File ID: {self.file_id}")
            logger.info(f"  - Filename: {data['filename']}")
            logger.info(f"  - Size: {data['size']} bytes")
            return True

        except RequestException as e:
            logger.error(f"❌ File upload failed: {e}")
            if hasattr(e.response, "text"):
                logger.error(f"Response: {e.response.text}")
            return False

    def test_start_translation(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Test starting a translation task"""
        if not self.file_id:
            logger.error("No file_id available. Upload a file first.")
            return False

        try:
            logger.info("Testing translation start...")

            # Default configuration
            default_config = {
                "service": "gpt-4o-mini",
                "lang_from": "English",
                "lang_to": "Simplified Chinese",
                "page_range": "First",  # Only translate first page for testing
                "threads": 4,
                "no_mono": False,
                "no_dual": False,
                "watermark_output_mode": "No Watermark",
                "no_auto_extract_glossary": True,
                "translate_table_text": True,
                "engine_settings": {},
            }

            # Merge with provided config
            if config:
                default_config.update(config)

            request_data = {"file_id": self.file_id, "config": default_config}

            response = self.session.post(f"{self.base_url}/api/translate", json=request_data)

            response.raise_for_status()
            data = response.json()
            self.task_id = data["task_id"]

            logger.info(f"✅ Translation started successfully:")
            logger.info(f"  - Task ID: {self.task_id}")
            logger.info(f"  - Status: {data['status']}")
            return True

        except RequestException as e:
            logger.error(f"❌ Translation start failed: {e}")
            if hasattr(e.response, "text"):
                logger.error(f"Response: {e.response.text}")
            return False

    def test_poll_status(self, timeout: int = 300, interval: int = 2) -> bool:
        """Test polling for translation status"""
        if not self.task_id:
            logger.error("No task_id available. Start a translation first.")
            return False

        try:
            logger.info("Testing status polling...")
            start_time = time.time()

            while time.time() - start_time < timeout:
                response = self.session.get(f"{self.base_url}/api/task/{self.task_id}/status")
                response.raise_for_status()
                status = response.json()

                # Log progress
                progress = status.get("progress", 0)
                stage = status.get("stage", "Unknown")
                logger.info(f"  Progress: {progress}% - {stage}")

                # Check if completed
                if status["status"] == "completed":
                    logger.info("✅ Translation completed successfully!")
                    result = status.get('result', {})
                    logger.info(f"  Result: {json.dumps(result, indent=2)}")
                    
                    # Check storage results
                    storage = result.get('storage', {})
                    if storage:
                        logger.info("  📦 Object Storage Results:")
                        for file_type, storage_info in storage.items():
                            logger.info(f"    - {file_type}: {storage_info.get('access_url', 'No URL')}")
                    else:
                        logger.warning("  ⚠️  No object storage results found")
                        logger.warning("     Check that ENABLE_OBJECT_STORAGE, STORAGE_API_URL, and STORAGE_API_TOKEN are set")
                    
                    return True

                # Check if failed
                elif status["status"] in ["error", "cancelled"]:
                    logger.error(f"❌ Translation failed: {status.get('error', 'Unknown error')}")
                    return False

                time.sleep(interval)

            logger.error("❌ Translation timed out")
            return False

        except RequestException as e:
            logger.error(f"❌ Status polling failed: {e}")
            return False

    def test_download_results(self, output_dir: Path) -> bool:
        """Test downloading translation results"""
        if not self.task_id:
            logger.error("No task_id available. Complete a translation first.")
            return False

        try:
            logger.info("Testing result download...")
            success = True

            for file_type in ["mono", "dual"]:
                try:
                    response = self.session.get(f"{self.base_url}/api/task/{self.task_id}/download/{file_type}")
                    response.raise_for_status()

                    # Save file
                    output_path = output_dir / f"translated_{file_type}_{self.task_id}.pdf"
                    with open(output_path, "wb") as f:
                        f.write(response.content)

                    logger.info(f"✅ Downloaded {file_type} PDF: {output_path}")
                    logger.info(f"  - Size: {len(response.content)} bytes")

                except RequestException as e:
                    if hasattr(e.response, "status_code") and e.response.status_code == 404:
                        logger.warning(f"⚠️  {file_type} PDF not generated (might be disabled)")
                    else:
                        logger.error(f"❌ Download {file_type} failed: {e}")
                        success = False

            return success

        except Exception as e:
            logger.error(f"❌ Download failed: {e}")
            return False

    def test_cleanup_file(self) -> bool:
        """Test cleaning up uploaded file"""
        if not self.file_id:
            logger.warning("No file_id to clean up")
            return True

        try:
            logger.info("Testing file cleanup...")
            response = self.session.delete(f"{self.base_url}/api/files/{self.file_id}")
            response.raise_for_status()
            data = response.json()

            logger.info(f"✅ File cleaned up: {data['message']}")
            return True

        except RequestException as e:
            logger.error(f"❌ Cleanup failed: {e}")
            return False

    def test_cleanup_task(self) -> bool:
        """Test cleaning up task data"""
        if not self.task_id:
            logger.warning("No task_id to clean up")
            return True

        try:
            logger.info("Testing task cleanup...")
            response = self.session.delete(f"{self.base_url}/api/task/{self.task_id}")
            response.raise_for_status()
            data = response.json()

            logger.info(f"✅ Task cleaned up: {data['status']}")
            return True

        except RequestException as e:
            logger.error(f"❌ Task cleanup failed: {e}")
            return False

    def run_full_workflow(self, pdf_path: Path, output_dir: Path, config: Optional[Dict[str, Any]] = None, skip_cleanup: bool = False) -> bool:
        """Run the complete API workflow test"""
        logger.info("=" * 60)
        logger.info("Starting PDFMathTranslate API Workflow Test")
        logger.info("=" * 60)

        # Track test results
        results = {
            "health_check": False,
            "get_languages": False,
            "get_services": False,
            "upload_file": False,
            "start_translation": False,
            "poll_status": False,
            "download_results": False,
            "cleanup_file": False,
            "cleanup_task": False,
        }

        try:
            # Run tests in sequence
            results["health_check"] = self.test_health_check()
            results["get_languages"] = self.test_get_languages()
            results["get_services"] = self.test_get_services()

            if results["health_check"]:
                results["upload_file"] = self.test_upload_file(pdf_path)

                if results["upload_file"]:
                    results["start_translation"] = self.test_start_translation(config)

                    if results["start_translation"]:
                        results["poll_status"] = self.test_poll_status()

                        if results["poll_status"]:
                            results["download_results"] = self.test_download_results(output_dir)

            # Cleanup (optional)
            if not skip_cleanup:
                results["cleanup_file"] = self.test_cleanup_file()
                results["cleanup_task"] = self.test_cleanup_task()

        except KeyboardInterrupt:
            logger.warning("\n⚠️  Test interrupted by user")
        except Exception as e:
            logger.error(f"\n❌ Unexpected error: {e}")

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("Test Summary:")
        logger.info("=" * 60)

        passed = sum(1 for v in results.values() if v)
        total = len(results)

        for test_name, passed in results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            logger.info(f"{test_name:.<40} {status}")

        logger.info("-" * 60)
        logger.info(f"Total: {passed}/{total} tests passed")

        return passed == total


def create_test_pdf(output_path: Path) -> None:
    """Create a simple test PDF file"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(str(output_path), pagesize=letter)
        c.drawString(100, 750, "PDFMathTranslate API Test Document")
        c.drawString(100, 700, "This is a test document for API testing.")
        c.drawString(100, 650, "Mathematics: E = mc²")
        c.drawString(100, 600, "Table test:")

        # Simple table
        data = [["Header 1", "Header 2", "Header 3"], ["Cell 1", "Cell 2", "Cell 3"], ["Data A", "Data B", "Data C"]]

        y = 550
        for row in data:
            x = 100
            for cell in row:
                c.drawString(x, y, cell)
                x += 100
            y -= 20

        c.save()
        logger.info(f"✅ Created test PDF: {output_path}")

    except ImportError:
        logger.warning("reportlab not installed. Please provide a test PDF file.")
        raise


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Test PDFMathTranslate API workflow")
    parser.add_argument("--pdf", type=Path, help="Path to test PDF file (will create one if not provided)")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL (default: http://localhost:8000)")
    parser.add_argument("--output-dir", type=Path, default=Path("test_output"), help="Directory for downloaded files (default: test_output)")
    parser.add_argument("--skip-cleanup", action="store_true", help="Skip cleanup steps")
    parser.add_argument("--config", type=json.loads, help="Translation config as JSON string")

    args = parser.parse_args()

    # Create output directory
    args.output_dir.mkdir(exist_ok=True)

    # Handle test PDF
    if args.pdf:
        pdf_path = args.pdf
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            sys.exit(1)
    else:
        # Create a test PDF
        pdf_path = args.output_dir / "test_document.pdf"
        try:
            create_test_pdf(pdf_path)
        except Exception as e:
            logger.error(f"Failed to create test PDF: {e}")
            logger.error("Please provide a PDF file using --pdf option")
            sys.exit(1)

    # Run tests
    tester = PDFTranslateAPITester(args.api_url)
    success = tester.run_full_workflow(pdf_path=pdf_path, output_dir=args.output_dir, config=args.config, skip_cleanup=args.skip_cleanup)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
