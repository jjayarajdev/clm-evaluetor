"""Regression tests for JWT decode hardening (2026-08-04 code review).

Covers: required exp/sub claims, token-type enforcement, algorithm pinning,
clock-skew leeway, and graceful handling of malformed/wrong-secret tokens
(None, never a 500).
"""

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import settings
from app.core.security import ACCESS_TOKEN_TYPE, create_access_token, decode_token, verify_token


def _encode(payload: dict, key: str | None = None, algorithm: str = "HS256") -> str:
    return jwt.encode(payload, key or settings.jwt_secret_key, algorithm=algorithm)


def _base_claims(**overrides) -> dict:
    claims = {
        "sub": "user-1",
        "username": "alice",
        "role": "admin",
        "tenant_id": "t-1",
        "business_unit_id": None,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "type": ACCESS_TOKEN_TYPE,
    }
    claims.update(overrides)
    return claims


class TestValidToken:
    def test_roundtrip(self):
        token = create_access_token("user-1", "alice", "admin", tenant_id="t-1")
        payload = decode_token(token)
        assert payload is not None
        assert payload.sub == "user-1"
        assert payload.role == "admin"

    def test_verify_token_returns_raw_payload(self):
        token = create_access_token("user-1", "alice", "admin")
        raw = verify_token(token)
        assert raw is not None
        assert raw["type"] == ACCESS_TOKEN_TYPE


class TestRejections:
    def test_wrong_type_rejected(self):
        # A signature-valid token that is not an access token must be refused.
        token = _encode(_base_claims(type="refresh"))
        assert decode_token(token) is None
        assert verify_token(token) is None

    def test_missing_type_rejected(self):
        claims = _base_claims()
        del claims["type"]
        assert decode_token(_encode(claims)) is None

    def test_missing_sub_rejected(self):
        claims = _base_claims()
        del claims["sub"]
        assert decode_token(_encode(claims)) is None

    def test_missing_exp_rejected(self):
        claims = _base_claims()
        del claims["exp"]
        assert decode_token(_encode(claims)) is None

    def test_expired_rejected(self):
        token = _encode(_base_claims(exp=datetime.now(timezone.utc) - timedelta(hours=1)))
        assert decode_token(token) is None

    def test_wrong_secret_rejected(self):
        token = _encode(_base_claims(), key="a-different-secret-entirely")
        assert decode_token(token) is None

    def test_alg_none_rejected(self):
        # alg=none must never be accepted. jose refuses to even encode it, so
        # hand-build the unsigned token (header.payload.) and confirm decode
        # rejects it rather than trusting an unsigned payload.
        import base64
        import json

        def b64(d: dict) -> str:
            return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

        header = b64({"alg": "none", "typ": "JWT"})
        body = b64({"sub": "u", "exp": 9999999999, "type": ACCESS_TOKEN_TYPE, "username": "x", "role": "admin"})
        forged = f"{header}.{body}."
        assert decode_token(forged) is None
        assert verify_token(forged) is None

    def test_garbage_returns_none_not_raise(self):
        assert decode_token("not.a.jwt") is None
        assert verify_token("") is None

    def test_signature_valid_but_missing_username_returns_none(self):
        # exp+sub present (pass jose require) but username absent → TokenPayload
        # build would KeyError; must degrade to None, not 500.
        claims = {"sub": "u", "exp": datetime.now(timezone.utc) + timedelta(hours=1), "type": ACCESS_TOKEN_TYPE}
        assert decode_token(_encode(claims)) is None


class TestClockSkew:
    def test_small_skew_tolerated(self):
        # Expired 5s ago — inside the 10s leeway, still valid.
        token = _encode(_base_claims(exp=datetime.now(timezone.utc) - timedelta(seconds=5)))
        assert decode_token(token) is not None

    def test_large_skew_rejected(self):
        token = _encode(_base_claims(exp=datetime.now(timezone.utc) - timedelta(seconds=60)))
        assert decode_token(token) is None
