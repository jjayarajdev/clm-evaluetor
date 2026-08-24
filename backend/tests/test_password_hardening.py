"""Regression tests for password-handling hardening (2026-08-24).

Covers: verify_password never raising on empty/malformed stored hashes (a bad
hash must read as "wrong password", not a 500 on login), the bcrypt 72-byte
cap enforced at hash time and in the password-setting schemas, and the
timing-equalization hash being a real, non-matching bcrypt hash.
"""

import pytest
from pydantic import ValidationError

from app.core.security import (
    BCRYPT_MAX_PASSWORD_BYTES,
    TIMING_EQUALIZATION_HASH,
    hash_password,
    verify_password,
)
from app.schemas.auth import PasswordChangeRequest
from app.schemas.user import UserPasswordUpdate


class TestVerifyPasswordRobustness:
    def test_roundtrip(self):
        assert verify_password("s3cret-pass", hash_password("s3cret-pass"))

    def test_wrong_password(self):
        assert not verify_password("wrong-pass", hash_password("s3cret-pass"))

    def test_empty_hash_returns_false_not_500(self):
        assert not verify_password("anything-here", "")

    def test_malformed_hash_returns_false_not_500(self):
        assert not verify_password("anything-here", "not-a-bcrypt-hash")

    def test_truncated_hash_returns_false_not_500(self):
        good = hash_password("s3cret-pass")
        assert not verify_password("s3cret-pass", good[:20])


class TestBcryptByteLimit:
    def test_hash_rejects_over_72_bytes(self):
        with pytest.raises(ValueError):
            hash_password("a" * (BCRYPT_MAX_PASSWORD_BYTES + 1))

    def test_hash_accepts_exactly_72_bytes(self):
        password = "a" * BCRYPT_MAX_PASSWORD_BYTES
        assert verify_password(password, hash_password(password))

    def test_multibyte_counted_in_bytes_not_chars(self):
        # 30 chars but 90 utf-8 bytes — must be rejected.
        with pytest.raises(ValueError):
            hash_password("é" * 45)

    def test_schema_rejects_long_new_password(self):
        with pytest.raises(ValidationError):
            UserPasswordUpdate(new_password="a" * 80)
        with pytest.raises(ValidationError):
            PasswordChangeRequest(
                current_password="current-pass", new_password="a" * 80
            )

    def test_schema_accepts_normal_password(self):
        assert UserPasswordUpdate(new_password="normal-pass-123")


class TestTimingEqualizationHash:
    def test_is_a_real_bcrypt_hash(self):
        # verify_password must exercise the full bcrypt cost against it (that
        # is the point — equal work whether or not the user exists).
        assert TIMING_EQUALIZATION_HASH.startswith("$2b$12$")
        assert not verify_password("any-guess-at-all", TIMING_EQUALIZATION_HASH)
