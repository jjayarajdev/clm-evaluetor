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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.models.contract import Contract, ContractStatus
from app.models.client import Client

logger = get_logger(__name__)


def compute_content_hash(content: bytes) -> str:
    """Compute SHA256 hash of file content.

    Args:
        content: File content as bytes.

    Returns:
        Hex digest of SHA256 hash.
    """
    return hashlib.sha256(content).hexdigest()


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe filesystem storage.

    Args:
        filename: Original filename.

    Returns:
        Sanitized filename safe for filesystem.
    """
    # Keep alphanumeric, dash, underscore, dot, space
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. ")
    sanitized = "".join(c if c in safe_chars else "_" for c in filename)
    # Replace multiple underscores/spaces with single
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    while "  " in sanitized:
        sanitized = sanitized.replace("  ", " ")
    return sanitized.strip()


def generate_folder_name(prefix: str = "") -> str:
    """Generate a unique folder name.

    Args:
        prefix: Optional prefix (e.g., counterparty name).

    Returns:
        Unique folder name with timestamp and UUID.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    if prefix:
        safe_prefix = sanitize_filename(prefix)[:50]
        return f"{safe_prefix}_{timestamp}_{unique_id}"
    return f"{timestamp}_{unique_id}"


# Allowed MIME types
ALLOWED_MIME_TYPES = {
    # Documents
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    # Spreadsheets
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
    # Presentations
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.ms-powerpoint": ".ppt",
}

# Allowed extensions (fallback)
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"}


def _get_mime_type_for_extension(ext: str) -> str:
    """Get MIME type for a file extension."""
    mime_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".ppt": "application/vnd.ms-powerpoint",
    }
    return mime_map.get(ext, "application/octet-stream")


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

    def create_contract_folder(self, prefix: str = "") -> Path:
        """Create a unique folder for a contract.

        Args:
            prefix: Optional prefix (e.g., counterparty name).

        Returns:
            Path to the created folder.
        """
        folder_name = generate_folder_name(prefix)
        folder_path = self.upload_dir / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)
        return folder_path

    def create_client_folder(self, client_code: str) -> Path:
        """Create a folder for a client with date subfolder.

        Structure: storage/uploads/{client_code}/{YYYYMMDD}/

        Args:
            client_code: Client's short code (e.g., "ING").

        Returns:
            Path to the created folder.
        """
        date_str = datetime.now().strftime("%Y%m%d")
        safe_code = sanitize_filename(client_code).upper()
        folder_path = self.upload_dir / safe_code / date_str
        folder_path.mkdir(parents=True, exist_ok=True)
        return folder_path

    async def check_duplicate_for_client(
        self,
        content_hash: str,
        filename: str,
        client_id: str | None,
        user_id: str,
    ) -> tuple[str, Contract | None]:
        """Check for duplicates within a client's contracts.

        Returns:
            Tuple of (action, existing_contract) where action is:
            - "create": No duplicate, create new contract
            - "reject": Exact duplicate (same hash), reject upload
            - "version": Same filename but different content, create new version

        Args:
            content_hash: SHA256 hash of the file content.
            filename: Original filename.
            client_id: Client ID (or None for unassigned).
            user_id: User ID.

        Returns:
            Action to take and existing contract if found.
        """
        # Build base query for the client's contracts
        base_query = select(Contract).where(Contract.uploaded_by == uuid.UUID(user_id))
        if client_id:
            base_query = base_query.where(Contract.client_id == uuid.UUID(client_id))

        # Check 1: Exact duplicate by content hash
        hash_query = base_query.where(Contract.content_hash == content_hash)
        result = await self.db.execute(hash_query.order_by(Contract.created_at.desc()).limit(1))
        existing_by_hash = result.scalar_one_or_none()

        if existing_by_hash:
            logger.info(f"Exact duplicate found: {existing_by_hash.filename} (hash match)")
            return "reject", existing_by_hash

        # Check 2: Same filename but different content (version update)
        name_query = base_query.where(Contract.filename == filename)
        result = await self.db.execute(name_query.order_by(Contract.version.desc()).limit(1))
        existing_by_name = result.scalar_one_or_none()

        if existing_by_name:
            logger.info(f"Same filename found with different content: {filename} (v{existing_by_name.version})")
            return "version", existing_by_name

        # No duplicate
        return "create", None

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

    async def save_file(
        self,
        file: UploadFile,
        content: bytes | None = None,
        folder_path: Path | None = None,
        preserve_filename: bool = True,
    ) -> tuple[str, str, int, str]:
        """Save an uploaded file to disk.

        Args:
            file: The uploaded file.
            content: Optional pre-read content (to avoid reading twice).
            folder_path: Optional folder to save in (creates new folder if None).
            preserve_filename: If True, keep original filename (sanitized). If False, generate unique name.

        Returns:
            Tuple of (filename, file_path, file_size, content_hash).
        """
        # Create folder if not provided
        if folder_path is None:
            folder_path = self.create_contract_folder()

        # Determine filename
        original_name = file.filename or "unknown"
        if preserve_filename:
            # Sanitize but keep original name
            filename = sanitize_filename(original_name)
            # If file exists, add a suffix
            file_path = folder_path / filename
            if file_path.exists():
                stem = Path(filename).stem
                ext = Path(filename).suffix
                counter = 1
                while file_path.exists():
                    filename = f"{stem}_{counter}{ext}"
                    file_path = folder_path / filename
                    counter += 1
        else:
            filename = self.generate_unique_filename(original_name)

        file_path = folder_path / filename

        # Read content if not provided
        if content is None:
            content = await file.read()

        file_size = len(content)
        content_hash = compute_content_hash(content)

        with open(file_path, "wb") as f:
            f.write(content)

        return filename, str(file_path), file_size, content_hash

    def get_contract_folder(self, file_path: str) -> Path:
        """Get the folder containing a contract file.

        Args:
            file_path: Path to the contract file.

        Returns:
            Path to the containing folder.
        """
        return Path(file_path).parent

    def list_folder_files(self, folder_path: Path | str) -> list[dict]:
        """List all files in a contract folder.

        Args:
            folder_path: Path to the folder.

        Returns:
            List of file info dicts with name, size, and path.
        """
        folder = Path(folder_path)
        if not folder.exists():
            return []

        files = []
        for f in folder.iterdir():
            if f.is_file():
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "path": str(f),
                    "extension": f.suffix.lower(),
                })
        return sorted(files, key=lambda x: x["name"])

    async def rename_contract_folder(
        self,
        contract: Contract,
        new_prefix: str,
    ) -> str | None:
        """Rename contract folder with counterparty prefix.

        Args:
            contract: The contract record.
            new_prefix: New prefix (usually counterparty name).

        Returns:
            New file path if renamed, None if not.
        """
        if not contract.file_path:
            return None

        current_folder = Path(contract.file_path).parent
        if not current_folder.exists():
            return None

        # Generate new folder name
        new_folder_name = generate_folder_name(new_prefix)
        new_folder_path = self.upload_dir / new_folder_name

        # Skip if already has the prefix
        if current_folder.name.startswith(sanitize_filename(new_prefix)[:20]):
            return None

        # Rename folder
        try:
            current_folder.rename(new_folder_path)

            # Update file path
            filename = Path(contract.file_path).name
            new_file_path = new_folder_path / filename

            return str(new_file_path)
        except Exception:
            return None

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
        existing_folder: Path | None = None,
    ) -> Contract:
        """Upload a single file and create a contract record.

        Args:
            file: The uploaded file.
            user_id: ID of the user uploading.
            allow_duplicate: If False, raises error for duplicate filenames.
            existing_folder: Optional existing folder to add file to.

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

        # Create folder or use existing
        if existing_folder:
            folder_path = existing_folder
        else:
            folder_path = self.create_contract_folder()

        # Save file (pass content to avoid reading again)
        filename, file_path, file_size, _ = await self.save_file(
            file, content, folder_path=folder_path, preserve_filename=True
        )

        # Determine MIME type
        ext = Path(file.filename or "").suffix.lower()
        mime_type = file.content_type
        if not mime_type:
            mime_type = _get_mime_type_for_extension(ext)

        # Create contract record
        contract = Contract(
            filename=file.filename or filename,
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
        group_in_folder: bool = False,
        folder_name: str | None = None,
    ) -> tuple[str, list[Contract], list[tuple[str, str]]]:
        """Upload multiple files.

        Args:
            files: List of uploaded files.
            user_id: ID of the user uploading.
            group_in_folder: If True, all files go into one folder (related documents).
            folder_name: Optional name for the shared folder.

        Returns:
            Tuple of (batch_id, successful_contracts, failed_files).
        """
        batch_id = uuid.uuid4().hex[:16]
        successful = []
        failed = []

        # Create shared folder if grouping
        shared_folder = None
        if group_in_folder:
            shared_folder = self.create_contract_folder(folder_name or "batch")

        for file in files:
            try:
                contract = await self.upload_single(
                    file, user_id, existing_folder=shared_folder
                )
                successful.append(contract)
            except UploadError as e:
                failed.append((file.filename or "unknown", str(e)))
            except Exception as e:
                failed.append((file.filename or "unknown", f"Unexpected error: {str(e)}"))

        return batch_id, successful, failed

    async def upload_for_client(
        self,
        files: list[UploadFile],
        user_id: str,
        client_id: str,
    ) -> tuple[str, list[Contract], list[tuple[str, str]]]:
        """Upload files for a specific client with versioning support.

        Files are stored in: storage/uploads/{client_code}/{YYYYMMDD}/

        Duplicate handling:
        - Same hash: Reject (exact duplicate)
        - Same filename, different hash: Create new version

        Args:
            files: List of uploaded files.
            user_id: ID of the user uploading.
            client_id: ID of the client.

        Returns:
            Tuple of (batch_id, successful_contracts, failed_files).
        """
        batch_id = uuid.uuid4().hex[:16]
        successful = []
        failed = []

        # Get client for folder naming
        result = await self.db.execute(
            select(Client).where(Client.id == uuid.UUID(client_id))
        )
        client = result.scalar_one_or_none()

        if not client:
            raise UploadError(f"Client not found: {client_id}")

        # Create client folder
        folder_path = self.create_client_folder(client.code)
        logger.info(f"Uploading {len(files)} files for client {client.code} to {folder_path}")

        for file in files:
            try:
                # Validate file
                is_valid, error = self.validate_file(file)
                if not is_valid:
                    failed.append((file.filename or "unknown", error))
                    continue

                # Read content for hash
                content = await file.read()
                content_hash = compute_content_hash(content)
                filename = file.filename or "unknown"

                # Check for duplicates within this client
                action, existing = await self.check_duplicate_for_client(
                    content_hash, filename, client_id, user_id
                )

                if action == "reject":
                    failed.append((
                        filename,
                        f"Exact duplicate of '{existing.filename}' uploaded on "
                        f"{existing.created_at.strftime('%Y-%m-%d %H:%M')}"
                    ))
                    continue

                # Save file
                saved_filename = sanitize_filename(filename)
                file_path = folder_path / saved_filename

                # Handle filename collision on disk
                if file_path.exists():
                    stem = Path(saved_filename).stem
                    ext = Path(saved_filename).suffix
                    counter = 1
                    while file_path.exists():
                        saved_filename = f"{stem}_{counter}{ext}"
                        file_path = folder_path / saved_filename
                        counter += 1

                with open(file_path, "wb") as f:
                    f.write(content)

                # Determine version
                version = 1
                previous_version_id = None
                if action == "version" and existing:
                    version = existing.version + 1
                    previous_version_id = existing.id
                    logger.info(f"Creating version {version} of {filename}")

                # Determine MIME type
                ext = Path(filename).suffix.lower()
                mime_type = file.content_type or _get_mime_type_for_extension(ext)

                # Create contract record
                contract = Contract(
                    filename=filename,
                    file_path=str(file_path),
                    file_size=len(content),
                    mime_type=mime_type,
                    content_hash=content_hash,
                    status=ContractStatus.PENDING,
                    uploaded_by=uuid.UUID(user_id),
                    client_id=uuid.UUID(client_id),
                    version=version,
                    previous_version_id=previous_version_id,
                )

                self.db.add(contract)
                await self.db.flush()
                await self.db.refresh(contract)
                successful.append(contract)

                logger.info(f"Uploaded: {filename} (v{version}) -> {file_path}")

            except UploadError as e:
                failed.append((file.filename or "unknown", str(e)))
            except Exception as e:
                logger.exception(f"Upload failed for {file.filename}: {e}")
                failed.append((file.filename or "unknown", f"Unexpected error: {str(e)}"))

        return batch_id, successful, failed

    async def extract_zip(
        self,
        zip_file: UploadFile,
        user_id: str,
        group_in_folder: bool = True,
    ) -> tuple[str, list[Contract], list[tuple[str, str]]]:
        """Extract and upload files from a ZIP archive.

        Args:
            zip_file: The uploaded ZIP file.
            user_id: ID of the user uploading.
            group_in_folder: If True, preserve ZIP folder structure or group flat files.

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
                # Group files by their top-level folder in the ZIP
                # Files at root level get their own folder
                folder_map: dict[str, Path] = {}

                for name in zf.namelist():
                    # Skip directories and hidden files
                    if name.endswith("/") or name.startswith("__") or "/." in name:
                        continue

                    # Skip macOS metadata
                    if "__MACOSX" in name or ".DS_Store" in name:
                        continue

                    ext = Path(name).suffix.lower()
                    if ext not in ALLOWED_EXTENSIONS:
                        failed.append((name, f"Unsupported file type: {ext}"))
                        continue

                    try:
                        # Determine folder key (top-level folder in ZIP or filename for root files)
                        parts = Path(name).parts
                        if len(parts) > 1:
                            # Has a folder - use first folder name
                            folder_key = parts[0]
                        else:
                            # Root level file - use filename stem as folder
                            folder_key = Path(name).stem

                        # Create or get folder
                        if folder_key not in folder_map:
                            folder_map[folder_key] = self.create_contract_folder(folder_key)

                        folder_path = folder_map[folder_key]

                        # Determine target filename (preserve structure within folder)
                        if len(parts) > 1:
                            # Keep relative path within the folder
                            relative_path = Path(*parts[1:])
                            target_filename = sanitize_filename(str(relative_path))
                        else:
                            target_filename = sanitize_filename(Path(name).name)

                        # Extract to target location
                        target_path = folder_path / target_filename
                        target_path.parent.mkdir(parents=True, exist_ok=True)

                        with zf.open(name) as src, open(target_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)

                        # Get file size
                        file_size = target_path.stat().st_size

                        # Check size limit
                        if file_size > settings.max_upload_size_mb * 1024 * 1024:
                            target_path.unlink()
                            failed.append((name, f"File too large: {file_size / 1024 / 1024:.1f}MB"))
                            continue

                        # Determine MIME type
                        mime_type = _get_mime_type_for_extension(ext)

                        # Compute hash
                        with open(target_path, "rb") as f:
                            file_content = f.read()
                            content_hash = compute_content_hash(file_content)

                        # Create contract record
                        contract = Contract(
                            filename=Path(name).name,
                            file_path=str(target_path),
                            file_size=file_size,
                            mime_type=mime_type,
                            content_hash=content_hash,
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
