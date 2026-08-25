"""Application-level encryption for secrets stored in the database.

Used by the EncryptedJSON column type (integration credentials). The Fernet
key is derived from CREDENTIALS_ENCRYPTION_KEY, falling back to
JWT_SECRET_KEY — set the dedicated key in production so rotating JWT
signing keys can never orphan stored credentials. Rotating the effective
key makes previously-encrypted values unreadable (they decrypt to None and
must be re-entered), so treat it like a data migration, not a routine
rotation.
"""

import base64
import hashlib
import json
import logging

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator

logger = logging.getLogger(__name__)

# Marker key for encrypted payloads. Legacy rows written before encryption
# are plain JSON objects without it and are still readable (lazy migration:
# they encrypt on their next save; scripts/encrypt_credentials.py force-saves).
_MARKER = "__enc__"


def _fernet() -> Fernet:
    from app.config import settings

    key_material = settings.credentials_encryption_key or settings.jwt_secret_key
    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_dict(value: dict) -> dict:
    """Encrypt a dict into the {"__enc__": token} envelope."""
    token = _fernet().encrypt(json.dumps(value).encode("utf-8")).decode("ascii")
    return {_MARKER: token}


def decrypt_dict(value: dict) -> dict | None:
    """Decrypt an envelope produced by encrypt_dict.

    Returns the original dict, or None if the token doesn't verify (wrong or
    rotated key) — callers see "no credentials configured" rather than a 500.
    """
    try:
        return json.loads(_fernet().decrypt(value[_MARKER].encode("ascii")))
    except (InvalidToken, KeyError, ValueError):
        logger.warning(
            "Failed to decrypt stored credentials — encryption key changed? "
            "The credentials must be re-entered."
        )
        return None


def is_encrypted(value: dict) -> bool:
    return isinstance(value, dict) and _MARKER in value


class EncryptedJSON(TypeDecorator):
    """JSON(B) column transparently encrypted with Fernet.

    Stored shape is {"__enc__": "<fernet token>"}. Legacy plaintext rows
    (no marker) load unchanged so pre-encryption data stays readable.
    """

    impl = JSONB
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if is_encrypted(value):
            # Already an envelope (e.g. re-saving a row loaded with a broken
            # key) — never double-encrypt.
            return value
        return encrypt_dict(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if is_encrypted(value):
            return decrypt_dict(value)
        return value
