"""File upload service for contract documents."""

import hashlib
import os
import shutil
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.contract import Contract, ContractStatus


def compute_content_hash(content: bytes) -> str:
    """Compute SHA256 hash of file content.

    Args:
        content: File content as bytes.

    Returns:
        Hex digest of SHA256 hash.
    """
    return hashlib.sha256(content).hexdigest()


# Allowed MIME types
ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}

# Allowed extensions (fallback)
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


class UploadError(Exception):
    """Exception raised for upload errors."""

    pass


class UploadService:
    """Service for handling file uploads."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session."""
        self.db = db
        self.upload_dir = Path(settings.upload_dir)
        self.processed_dir = Path(settings.processed_dir)

        # Ensure directories exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def validate_file(self, file: UploadFile) -> tuple[bool, str]:
        """Validate an uploaded file.

        Args:
            file: The uploaded file.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if not file.filename:
            return False, "Filename is required"

        # Check extension
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"File type '{ext}' not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"

        # Check MIME type if available
        if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
            # Be lenient - some browsers send wrong MIME types
            if ext not in ALLOWED_EXTENSIONS:
                return False, f"Invalid file type: {file.content_type}"

        # Check file size (read size from file)
        if file.size and file.size > settings.max_upload_size_mb * 1024 * 1024:
            return False, f"File too large. Maximum size: {settings.max_upload_size_mb}MB"

        return True, ""

    def generate_unique_filename(self, original_filename: str) -> str:
        """Generate a unique filename preserving the extension.

        Args:
            original_filename: Original filename.

        Returns:
            Unique filename with UUID prefix.
        """
        ext = Path(original_filename).suffix.lower()
        unique_id = uuid.uuid4().hex[:12]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in Path(original_filename).stem if c.isalnum() or c in "-_")[:50]

        return f"{timestamp}_{unique_id}_{safe_name}{ext}"

    async def save_file(self, file: UploadFile, content: bytes | None = None) -> tuple[str, str, int, str]:
        """Save an uploaded file to disk.

        Args:
            file: The uploaded file.
            content: Optional pre-read content (to avoid reading twice).

        Returns:
            Tuple of (unique_filename, file_path, file_size, content_hash).
        """
        unique_filename = self.generate_unique_filename(file.filename or "unknown")
        file_path = self.upload_dir / unique_filename

        # Read content if not provided
        if content is None:
            content = await file.read()

        file_size = len(content)
        content_hash = compute_content_hash(content)

        with open(file_path, "wb") as f:
            f.write(content)

        return unique_filename, str(file_path), file_size, content_hash

    async def check_duplicate(
        self,
        content_hash: str,
        user_id: str,
        filename: str | None = None,
    ) -> Contract | None:
        """Check if a contract with the same content already exists for this user.

        Args:
            content_hash: SHA256 hash of the file content.
            user_id: ID of the user.
            filename: Optional filename for additional check.

        Returns:
            Existing Contract if duplicate found, None otherwise.
        """
        # Check by content hash (same file content)
        result = await self.db.execute(
            select(Contract)
            .where(Contract.content_hash == content_hash)
            .where(Contract.uploaded_by == uuid.UUID(user_id))
            .order_by(Contract.created_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        # Also check by filename (different content but same name - warn user)
        if filename:
            result = await self.db.execute(
                select(Contract)
                .where(Contract.filename == filename)
                .where(Contract.uploaded_by == uuid.UUID(user_id))
                .order_by(Contract.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

        return None

    async def upload_single(
        self,
        file: UploadFile,
        user_id: str,
        allow_duplicate: bool = False,
    ) -> Contract:
        """Upload a single file and create a contract record.

        Args:
            file: The uploaded file.
            user_id: ID of the user uploading.
            allow_duplicate: If False, raises error for duplicate filenames.

        Returns:
            Created Contract record.

        Raises:
            UploadError: If validation fails or duplicate exists.
        """
        # Validate
        is_valid, error = self.validate_file(file)
        if not is_valid:
            raise UploadError(error)

        # Read content first for hash computation
        content = await file.read()
        content_hash = compute_content_hash(content)

        # Check for duplicates by content hash
        if not allow_duplicate:
            existing = await self.check_duplicate(content_hash, user_id, file.filename)
            if existing:
                if existing.content_hash == content_hash:
                    raise UploadError(
                        f"This exact file was already uploaded as '{existing.filename}' "
                        f"on {existing.created_at.strftime('%Y-%m-%d %H:%M')}. "
                        f"Delete the existing contract to re-upload."
                    )
                else:
                    raise UploadError(
                        f"A contract with filename '{file.filename}' already exists "
                        f"(uploaded on {existing.created_at.strftime('%Y-%m-%d %H:%M')}). "
                        f"Delete the existing contract first or rename this file."
                    )

        # Save file (pass content to avoid reading again)
        unique_filename, file_path, file_size, _ = await self.save_file(file, content)

        # Determine MIME type
        ext = Path(file.filename or "").suffix.lower()
        mime_type = file.content_type
        if not mime_type:
            mime_type = "application/pdf" if ext == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        # Create contract record
        contract = Contract(
            filename=file.filename or unique_filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            content_hash=content_hash,
            status=ContractStatus.PENDING,
            uploaded_by=uuid.UUID(user_id),
        )

        self.db.add(contract)
        await self.db.flush()
        await self.db.refresh(contract)

        return contract

    async def upload_batch(
        self,
        files: list[UploadFile],
        user_id: str,
    ) -> tuple[str, list[Contract], list[tuple[str, str]]]:
        """Upload multiple files.

        Args:
            files: List of uploaded files.
            user_id: ID of the user uploading.

        Returns:
            Tuple of (batch_id, successful_contracts, failed_files).
        """
        batch_id = uuid.uuid4().hex[:16]
        successful = []
        failed = []

        for file in files:
            try:
                contract = await self.upload_single(file, user_id)
                successful.append(contract)
            except UploadError as e:
                failed.append((file.filename or "unknown", str(e)))
            except Exception as e:
                failed.append((file.filename or "unknown", f"Unexpected error: {str(e)}"))

        return batch_id, successful, failed

    async def extract_zip(
        self,
        zip_file: UploadFile,
        user_id: str,
    ) -> tuple[str, list[Contract], list[tuple[str, str]]]:
        """Extract and upload files from a ZIP archive.

        Args:
            zip_file: The uploaded ZIP file.
            user_id: ID of the user uploading.

        Returns:
            Tuple of (batch_id, successful_contracts, failed_files).
        """
        batch_id = uuid.uuid4().hex[:16]
        successful = []
        failed = []

        # Save ZIP temporarily
        temp_zip_path = self.upload_dir / f"temp_{batch_id}.zip"
        content = await zip_file.read()

        with open(temp_zip_path, "wb") as f:
            f.write(content)

        try:
            with zipfile.ZipFile(temp_zip_path, "r") as zf:
                for name in zf.namelist():
                    # Skip directories and hidden files
                    if name.endswith("/") or name.startswith("__") or "/." in name:
                        continue

                    ext = Path(name).suffix.lower()
                    if ext not in ALLOWED_EXTENSIONS:
                        failed.append((name, f"Unsupported file type: {ext}"))
                        continue

                    try:
                        # Extract to temp location
                        temp_path = self.upload_dir / f"temp_{uuid.uuid4().hex[:8]}_{Path(name).name}"
                        with zf.open(name) as src, open(temp_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)

                        # Get file size
                        file_size = temp_path.stat().st_size

                        # Check size limit
                        if file_size > settings.max_upload_size_mb * 1024 * 1024:
                            temp_path.unlink()
                            failed.append((name, f"File too large: {file_size / 1024 / 1024:.1f}MB"))
                            continue

                        # Generate unique filename and move
                        unique_filename = self.generate_unique_filename(Path(name).name)
                        final_path = self.upload_dir / unique_filename
                        temp_path.rename(final_path)

                        # Determine MIME type
                        mime_type = "application/pdf" if ext == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

                        # Create contract record
                        contract = Contract(
                            filename=Path(name).name,
                            file_path=str(final_path),
                            file_size=file_size,
                            mime_type=mime_type,
                            status=ContractStatus.PENDING,
                            uploaded_by=uuid.UUID(user_id),
                        )

                        self.db.add(contract)
                        await self.db.flush()
                        await self.db.refresh(contract)
                        successful.append(contract)

                    except Exception as e:
                        failed.append((name, str(e)))

        finally:
            # Clean up temp ZIP
            if temp_zip_path.exists():
                temp_zip_path.unlink()

        return batch_id, successful, failed

    async def get_upload_status(
        self,
        contract_ids: list[str],
    ) -> dict[str, int]:
        """Get status counts for a list of contracts.

        Args:
            contract_ids: List of contract IDs.

        Returns:
            Dictionary with status counts.
        """
        from sqlalchemy import func

        result = await self.db.execute(
            select(Contract.status, func.count(Contract.id))
            .where(Contract.id.in_([uuid.UUID(cid) for cid in contract_ids]))
            .group_by(Contract.status)
        )

        counts = {status.value: 0 for status in ContractStatus}
        for status, count in result.all():
            counts[status.value] = count

        return counts

    async def get_contracts_by_ids(
        self,
        contract_ids: list[str],
    ) -> list[Contract]:
        """Get contracts by their IDs.

        Args:
            contract_ids: List of contract IDs.

        Returns:
            List of Contract records.
        """
        result = await self.db.execute(
            select(Contract)
            .where(Contract.id.in_([uuid.UUID(cid) for cid in contract_ids]))
            .order_by(Contract.created_at.desc())
        )
        return list(result.scalars().all())

    def delete_file(self, file_path: str) -> bool:
        """Delete a file from disk.

        Args:
            file_path: Path to the file.

        Returns:
            True if deleted, False if not found.
        """
        path = Path(file_path)
        if path.exists():
            path.unlink()
            return True
        return False
