"""Tests for SecurityHeadersMiddleware (2026-08-24 hardening).

Headers must be present on every response (including 404s), the restrictive
CSP must not apply to the interactive API docs, and HSTS must only be sent
when the request arrived over TLS (directly or via X-Forwarded-Proto).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
class TestSecurityHeaders:
    async def test_headers_on_every_response(self):
        async with _client() as client:
            resp = await client.get("/api/this-route-does-not-exist")
        assert resp.status_code == 404
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "camera=()" in resp.headers["Permissions-Policy"]
        assert resp.headers["Content-Security-Policy"] == (
            "default-src 'none'; frame-ancestors 'none'"
        )

    async def test_docs_exempt_from_csp(self):
        async with _client() as client:
            resp = await client.get("/api/openapi.json")
        assert resp.status_code == 200
        assert "Content-Security-Policy" not in resp.headers
        # The other headers still apply to docs.
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

    async def test_no_hsts_over_plain_http(self):
        async with _client() as client:
            resp = await client.get("/api/this-route-does-not-exist")
        assert "Strict-Transport-Security" not in resp.headers

    async def test_hsts_when_forwarded_proto_https(self):
        async with _client() as client:
            resp = await client.get(
                "/api/this-route-does-not-exist",
                headers={"X-Forwarded-Proto": "https"},
            )
        assert resp.headers["Strict-Transport-Security"].startswith("max-age=")
