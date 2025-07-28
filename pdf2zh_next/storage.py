"""
Object storage integration for PDFMathTranslate
"""

import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class StorageConfig:
    """Storage service configuration"""

    enabled: bool = os.getenv("ENABLE_OBJECT_STORAGE", "true").lower() == "true"
    api_base_url: str = os.getenv("STORAGE_API_URL", "")
    auth_token: str = os.getenv("STORAGE_API_TOKEN", "")


@dataclass
class PresignedUrlResponse:
    """Response from presigned URL API"""

    presigned_url: str
    key: str
    expires_at: int
    access_url: str
    access_expires_at: int


class ObjectStorageClient:
    """Client for interacting with object storage service"""

    def __init__(self, config: StorageConfig | None = None):
        self.config = config or StorageConfig()
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    @property
    def session(self) -> aiohttp.ClientSession:
        if not self._session:
            raise RuntimeError("Session not initialized. Use async with statement.")
        return self._session

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content"""
        sha256_hash = hashlib.sha256()
        with Path.open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    async def get_presigned_url(self, filename: str) -> PresignedUrlResponse:
        """Get presigned URL for uploading file"""
        url = f"{self.config.api_base_url}/api/v1/storage/presigned-url"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.auth_token}",
            "Accept": "*/*",
        }
        data = {"filename": filename}

        async with self.session.post(url, headers=headers, json=data) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Failed to get presigned URL: {response.status} - {error_text}")

            result = await response.json()
            if result.get("code") != 0:
                raise Exception(f"API error: {result.get('msg', 'Unknown error')}")

            data = result["data"]
            return PresignedUrlResponse(
                presigned_url=data["presigned_url"],
                key=data["key"],
                expires_at=data["expires_at"],
                access_url=data["access_url"],
                access_expires_at=data["access_expires_at"],
            )

    async def upload_file(self, file_path: Path, presigned_url: str) -> None:
        """Upload file to presigned URL"""
        with Path.open(file_path, "rb") as f:
            file_data = f.read()

        # Important: Skip auto headers to avoid signature mismatch
        # aiohttp may auto-add Content-Type which breaks presigned URL signatures
        async with self.session.put(presigned_url, data=file_data, skip_auto_headers=["Content-Type"]) as response:
            if response.status not in (200, 201, 204):
                error_text = await response.text()
                raise Exception(f"Failed to upload file: {response.status} - {error_text}")

    async def upload_pdf_with_hash(self, file_path: Path) -> dict[str, Any]:
        """
        Upload PDF file to object storage using content hash as key

        Returns:
            Dict containing upload info including access_url and hash
        """
        # Calculate file hash
        file_hash = self._calculate_file_hash(file_path)
        logger.info(f"File hash: {file_hash}")

        # Use hash as part of filename to enable deduplication
        original_name = file_path.stem
        extension = file_path.suffix
        hash_filename = f"{original_name}_{file_hash[:8]}{extension}"

        # Get presigned URL
        presigned_response = await self.get_presigned_url(hash_filename)
        logger.info(f"Got presigned URL for key: {presigned_response.key}")

        # Upload file
        await self.upload_file(file_path, presigned_response.presigned_url)
        logger.info("File uploaded successfully")

        return {
            "file_hash": file_hash,
            "storage_key": presigned_response.key,
            "access_url": presigned_response.access_url,
            "access_expires_at": presigned_response.access_expires_at,
            "upload_time": datetime.utcnow().isoformat(),
        }


# Storage cache to track uploaded files by hash
_storage_cache: dict[str, dict[str, Any]] = {}


async def upload_to_storage(file_path: Path) -> dict[str, Any] | None:
    """
    Upload file to object storage with deduplication

    Uses file content hash to avoid duplicate uploads
    Returns None if storage is disabled
    """
    config = StorageConfig()
    if not config.enabled:
        logger.info("Object storage is disabled, skipping upload")
        return None

    async with ObjectStorageClient(config) as client:
        file_hash = client._calculate_file_hash(file_path)

        # Check if file already uploaded
        if file_hash in _storage_cache:
            logger.info("File already uploaded, reusing existing URL")
            return _storage_cache[file_hash]

        # Upload new file
        result = await client.upload_pdf_with_hash(file_path)

        # Cache result
        _storage_cache[file_hash] = result

        return result
