"""SSO (Single Sign-On) router — OIDC-based enterprise authentication.

Supports OpenID Connect with any compliant Identity Provider:
- Microsoft Entra ID (Azure AD)
- Okta
- Google Workspace
- Auth0, Keycloak, etc.

Flow:
1. Admin configures SSO (issuer, client_id, client_secret) per tenant
2. User clicks "Sign in with SSO" → GET /api/auth/sso/init?tenant_slug=xxx
3. Backend redirects to IdP authorization endpoint
4. IdP authenticates user → redirects to /api/auth/sso/callback with code
5. Backend exchanges code for tokens, extracts user info
6. Maps user to tenant, auto-provisions if needed, issues our JWT
7. Redirects to frontend with JWT in URL fragment
"""

import logging
import secrets
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.audit import log_audit
from app.core.security import create_access_token, hash_password
from app.database import get_db
from app.models.audit import AuditAction
from app.models.integration import IntegrationConfig, IntegrationSystem, IntegrationStatus
from app.models.tenant import Tenant
from app.models.user import User, Role
from app.core.deps import AdminUser, CurrentTenantId, RequiredTenantId, SuperAdminUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/sso", tags=["SSO Authentication"])

# In-memory state store for CSRF protection (use Redis in production)
_sso_states: dict[str, dict] = {}

# OIDC well-known configuration cache
_oidc_configs: dict[str, dict] = {}


# ── Pydantic Schemas ──────────────────────────────────────────────────


class SSOConfigCreate(BaseModel):
    """Request body for creating/updating SSO configuration."""

    name: str = Field(default="SSO", max_length=200)
    provider: str = Field(
        default="generic",
        description="Provider hint: azure_ad, okta, google, generic",
    )
    issuer_url: str = Field(
        ...,
        description="OIDC issuer URL (e.g. https://login.microsoftonline.com/{tenant}/v2.0)",
    )
    client_id: str = Field(..., description="OAuth2 client ID")
    client_secret: str = Field(..., description="OAuth2 client secret")
    scopes: list[str] = Field(
        default=["openid", "email", "profile"],
        description="OIDC scopes to request",
    )
    # User mapping
    default_role: str = Field(
        default="legal",
        description="Default role for auto-provisioned users",
    )
    auto_provision: bool = Field(
        default=True,
        description="Auto-create users on first SSO login",
    )
    # Optional: map IdP groups/roles to our roles
    role_mapping: Optional[dict[str, str]] = Field(
        default=None,
        description='Map IdP groups to roles, e.g. {"ContractAdmins": "admin", "Legal": "legal"}',
    )


class SSOConfigResponse(BaseModel):
    """SSO config response (secrets redacted)."""

    id: UUID
    name: str
    provider: str
    issuer_url: str
    client_id: str  # Not secret
    scopes: list[str]
    default_role: str
    auto_provision: bool
    role_mapping: Optional[dict[str, str]] = None
    is_active: bool
    health_status: str
    last_health_check: Optional[datetime] = None
    tenant_slug: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SSOInitResponse(BaseModel):
    """Response for SSO init — provides the redirect URL."""

    redirect_url: str
    state: str


class SSOTenantInfo(BaseModel):
    """Public info about a tenant's SSO availability."""

    tenant_slug: str
    tenant_name: str
    provider: str
    enabled: bool


# ── OIDC Discovery ────────────────────────────────────────────────────


async def _get_oidc_config(issuer_url: str) -> dict:
    """Fetch and cache the OIDC well-known configuration."""
    if issuer_url in _oidc_configs:
        return _oidc_configs[issuer_url]

    well_known_url = f"{issuer_url.rstrip('/')}/.well-known/openid-configuration"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(well_known_url)
        resp.raise_for_status()
        config = resp.json()

    _oidc_configs[issuer_url] = config
    return config


# ── Helpers ────────────────────────────────────────────────────────────


def _config_to_response(config: IntegrationConfig, tenant_slug: str | None = None) -> SSOConfigResponse:
    """Convert IntegrationConfig to SSOConfigResponse."""
    creds = config.credentials or {}
    cfg = config.config or {}
    return SSOConfigResponse(
        id=config.id,
        name=config.name,
        provider=cfg.get("provider", "generic"),
        issuer_url=creds.get("issuer_url", ""),
        client_id=creds.get("client_id", ""),
        scopes=cfg.get("scopes", ["openid", "email", "profile"]),
        default_role=cfg.get("default_role", "legal"),
        auto_provision=cfg.get("auto_provision", True),
        role_mapping=cfg.get("role_mapping"),
        is_active=config.is_active,
        health_status=config.health_status.value if hasattr(config.health_status, "value") else str(config.health_status),
        last_health_check=config.last_health_check,
        tenant_slug=tenant_slug,
        created_at=config.created_at,
    )


def _resolve_tenant_id(
    jwt_tenant_id: UUID | None,
    for_tenant_id: UUID | None,
    current_user,
) -> UUID:
    """Resolve effective tenant_id — super admin can target any tenant."""
    if for_tenant_id and current_user and current_user.role == Role.SUPER_ADMIN:
        return for_tenant_id
    if jwt_tenant_id:
        return jwt_tenant_id
    raise HTTPException(status_code=400, detail="tenant_id required (use for_tenant_id param)")


async def _get_sso_config_for_tenant(db: AsyncSession, tenant_id: UUID) -> IntegrationConfig | None:
    """Get active SSO config for a tenant."""
    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.tenant_id == tenant_id,
            IntegrationConfig.system == IntegrationSystem.sso_oidc,
            IntegrationConfig.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def _get_sso_config_by_slug(db: AsyncSession, tenant_slug: str) -> tuple[IntegrationConfig | None, Tenant | None]:
    """Get SSO config by tenant slug."""
    result = await db.execute(
        select(Tenant).where(Tenant.slug == tenant_slug, Tenant.is_active.is_(True))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        return None, None

    config = await _get_sso_config_for_tenant(db, tenant.id)
    return config, tenant


def _get_callback_url(request: Request) -> str:
    """Build the SSO callback URL from the current request."""
    # Use the origin from the request
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost"))
    return f"{scheme}://{host}/api/auth/sso/callback"


# ── Admin Configuration Endpoints ─────────────────────────────────────


@router.get("/config", response_model=Optional[SSOConfigResponse])
async def get_sso_config(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = None,
    for_tenant_id: Optional[UUID] = Query(None, description="Target tenant (super admin only)"),
):
    """Get SSO configuration for the current tenant (or specified tenant for super admin)."""
    effective_tenant_id = _resolve_tenant_id(tenant_id, for_tenant_id, current_user)
    config = await _get_sso_config_for_tenant(db, effective_tenant_id)
    if not config:
        return None

    # Get tenant slug
    tenant = await db.get(Tenant, effective_tenant_id)
    return _config_to_response(config, tenant.slug if tenant else None)


@router.post("/config", response_model=SSOConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_sso_config(
    body: SSOConfigCreate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = None,
    for_tenant_id: Optional[UUID] = Query(None, description="Target tenant (super admin only)"),
):
    """Create or update SSO configuration for the current tenant."""
    effective_tenant_id = _resolve_tenant_id(tenant_id, for_tenant_id, current_user)

    # Check for existing config
    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.tenant_id == effective_tenant_id,
            IntegrationConfig.system == IntegrationSystem.sso_oidc,
        )
    )
    config = result.scalar_one_or_none()

    credentials = {
        "issuer_url": body.issuer_url.rstrip("/"),
        "client_id": body.client_id,
        "client_secret": body.client_secret,
    }
    extra_config = {
        "provider": body.provider,
        "scopes": body.scopes,
        "default_role": body.default_role,
        "auto_provision": body.auto_provision,
        "role_mapping": body.role_mapping,
    }

    if config:
        config.name = body.name
        config.credentials = credentials
        config.config = extra_config
        config.is_active = True
        config.base_url = body.issuer_url.rstrip("/")
        config.auth_type = "oauth2"
    else:
        config = IntegrationConfig(
            id=uuid4(),
            tenant_id=effective_tenant_id,
            system=IntegrationSystem.sso_oidc,
            name=body.name,
            base_url=body.issuer_url.rstrip("/"),
            auth_type="oauth2",
            credentials=credentials,
            config=extra_config,
            is_active=True,
            health_status=IntegrationStatus.unknown,
        )
        db.add(config)

    # Clear OIDC config cache for this issuer
    _oidc_configs.pop(body.issuer_url.rstrip("/"), None)

    await db.flush()
    await db.commit()

    tenant = await db.get(Tenant, effective_tenant_id)
    return _config_to_response(config, tenant.slug if tenant else None)


@router.post("/config/test")
async def test_sso_config(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = None,
    for_tenant_id: Optional[UUID] = Query(None, description="Target tenant (super admin only)"),
):
    """Test SSO configuration by fetching OIDC discovery document."""
    effective_tenant_id = _resolve_tenant_id(tenant_id, for_tenant_id, current_user)
    config = await _get_sso_config_for_tenant(db, effective_tenant_id)
    if not config:
        raise HTTPException(status_code=404, detail="No SSO configuration found")

    creds = config.credentials or {}
    issuer_url = creds.get("issuer_url", "")

    try:
        oidc_config = await _get_oidc_config(issuer_url)

        # Verify required endpoints exist
        required = ["authorization_endpoint", "token_endpoint", "userinfo_endpoint"]
        missing = [k for k in required if k not in oidc_config]

        if missing:
            config.health_status = IntegrationStatus.unhealthy
            config.last_health_check = datetime.utcnow()
            config.last_health_message = f"Missing OIDC endpoints: {', '.join(missing)}"
            await db.commit()
            return {"healthy": False, "message": f"Missing OIDC endpoints: {', '.join(missing)}"}

        config.health_status = IntegrationStatus.healthy
        config.last_health_check = datetime.utcnow()
        config.last_health_message = f"OIDC discovery OK — {oidc_config.get('issuer', issuer_url)}"
        await db.commit()

        return {
            "healthy": True,
            "message": "OIDC discovery successful",
            "issuer": oidc_config.get("issuer"),
            "authorization_endpoint": oidc_config.get("authorization_endpoint"),
        }
    except Exception as e:
        config.health_status = IntegrationStatus.unhealthy
        config.last_health_check = datetime.utcnow()
        config.last_health_message = str(e)[:200]
        await db.commit()
        return {"healthy": False, "message": str(e)[:200]}


@router.delete("/config")
async def delete_sso_config(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = None,
    for_tenant_id: Optional[UUID] = Query(None, description="Target tenant (super admin only)"),
):
    """Deactivate SSO configuration."""
    effective_tenant_id = _resolve_tenant_id(tenant_id, for_tenant_id, current_user)
    config = await _get_sso_config_for_tenant(db, effective_tenant_id)
    if not config:
        raise HTTPException(status_code=404, detail="No SSO configuration found")

    config.is_active = False
    await db.commit()
    return {"status": "disabled"}


# ── Public SSO Endpoints (no auth required) ───────────────────────────


@router.get("/providers")
async def list_sso_providers(
    db: AsyncSession = Depends(get_db),
):
    """List tenants that have SSO enabled (public endpoint for login page)."""
    result = await db.execute(
        select(IntegrationConfig, Tenant).join(
            Tenant, IntegrationConfig.tenant_id == Tenant.id
        ).where(
            IntegrationConfig.system == IntegrationSystem.sso_oidc,
            IntegrationConfig.is_active.is_(True),
            Tenant.is_active.is_(True),
        )
    )

    providers = []
    for config, tenant in result.all():
        cfg = config.config or {}
        providers.append(SSOTenantInfo(
            tenant_slug=tenant.slug,
            tenant_name=tenant.name,
            provider=cfg.get("provider", "generic"),
            enabled=True,
        ))

    return providers


@router.get("/init")
async def sso_init(
    request: Request,
    tenant_slug: str = Query(..., description="Tenant slug to initiate SSO for"),
    db: AsyncSession = Depends(get_db),
):
    """Initiate SSO login flow — returns IdP authorization URL.

    The frontend redirects the user's browser to the returned URL.
    """
    config, tenant = await _get_sso_config_by_slug(db, tenant_slug)
    if not config or not tenant:
        raise HTTPException(
            status_code=404,
            detail=f"SSO not configured for tenant '{tenant_slug}'",
        )

    creds = config.credentials or {}
    cfg = config.config or {}
    issuer_url = creds.get("issuer_url", "")

    # Fetch OIDC discovery
    try:
        oidc_config = await _get_oidc_config(issuer_url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch OIDC config: {e}")

    auth_endpoint = oidc_config["authorization_endpoint"]
    scopes = cfg.get("scopes", ["openid", "email", "profile"])
    callback_url = _get_callback_url(request)

    # Generate CSRF state
    state = secrets.token_urlsafe(32)
    _sso_states[state] = {
        "tenant_id": str(tenant.id),
        "tenant_slug": tenant_slug,
        "config_id": str(config.id),
        "created_at": datetime.utcnow().isoformat(),
    }

    # Build authorization URL
    params = {
        "response_type": "code",
        "client_id": creds["client_id"],
        "redirect_uri": callback_url,
        "scope": " ".join(scopes),
        "state": state,
        "nonce": secrets.token_urlsafe(16),
    }
    query_string = "&".join(f"{k}={httpx.URL('', params={k: v}).params[k]}" for k, v in params.items())
    redirect_url = f"{auth_endpoint}?{query_string}"

    return SSOInitResponse(redirect_url=redirect_url, state=state)


@router.get("/callback")
async def sso_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle IdP callback — exchange code for tokens, map user, issue JWT.

    Redirects to frontend with JWT token.
    """
    # Validate state (CSRF protection)
    state_data = _sso_states.pop(state, None)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired SSO state")

    tenant_id = UUID(state_data["tenant_id"])
    config_id = UUID(state_data["config_id"])

    # Load config
    config = await db.get(IntegrationConfig, config_id)
    if not config or not config.is_active:
        raise HTTPException(status_code=400, detail="SSO configuration no longer active")

    creds = config.credentials or {}
    cfg = config.config or {}
    issuer_url = creds.get("issuer_url", "")

    # Get OIDC endpoints
    oidc_config = await _get_oidc_config(issuer_url)
    token_endpoint = oidc_config["token_endpoint"]
    userinfo_endpoint = oidc_config.get("userinfo_endpoint")

    callback_url = _get_callback_url(request)

    # Exchange authorization code for tokens
    try:
        async with httpx.AsyncClient(timeout=15) as http_client:
            token_resp = await http_client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": callback_url,
                    "client_id": creds["client_id"],
                    "client_secret": creds["client_secret"],
                },
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
    except Exception as e:
        logger.error(f"SSO token exchange failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to exchange authorization code")

    # Get user info from IdP
    access_token = token_data.get("access_token")
    id_token_raw = token_data.get("id_token")

    user_info = {}

    # Try userinfo endpoint first
    if userinfo_endpoint and access_token:
        try:
            async with httpx.AsyncClient(timeout=10) as http_client:
                ui_resp = await http_client.get(
                    userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if ui_resp.is_success:
                    user_info = ui_resp.json()
        except Exception as e:
            logger.warning(f"Userinfo endpoint failed: {e}")

    # Fallback: decode id_token (without full validation for simplicity)
    if not user_info and id_token_raw:
        try:
            import base64
            import json
            # Decode JWT payload (middle part)
            parts = id_token_raw.split(".")
            if len(parts) >= 2:
                # Add padding
                payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
                user_info = json.loads(base64.urlsafe_b64decode(payload))
        except Exception:
            pass

    if not user_info:
        raise HTTPException(status_code=502, detail="Could not retrieve user information from IdP")

    # Extract user attributes
    email = user_info.get("email") or user_info.get("preferred_username") or user_info.get("upn", "")
    full_name = user_info.get("name") or f"{user_info.get('given_name', '')} {user_info.get('family_name', '')}".strip()
    idp_groups = user_info.get("groups", [])

    if not email:
        raise HTTPException(status_code=400, detail="No email found in IdP response")

    # Determine role
    role_mapping = cfg.get("role_mapping") or {}
    mapped_role = cfg.get("default_role", "legal")
    for group_name, role_value in role_mapping.items():
        if group_name in idp_groups:
            mapped_role = role_value
            break

    # Find or create user
    result = await db.execute(
        select(User).where(
            User.email == email.lower(),
            User.tenant_id == tenant_id,
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        # Try matching by email across tenants (maybe user exists elsewhere)
        result = await db.execute(
            select(User).where(User.email == email.lower()).limit(1)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user and existing_user.tenant_id == tenant_id:
            user = existing_user

    if user:
        # Update user info from IdP
        if full_name and full_name != user.full_name:
            user.full_name = full_name
        if not user.is_active:
            raise HTTPException(status_code=403, detail="User account is deactivated")
    elif cfg.get("auto_provision", True):
        # Auto-provision new user
        # Generate a username from email
        username = email.split("@")[0].lower().replace(".", "_").replace("-", "_")

        # Check username uniqueness
        check = await db.execute(select(User.id).where(User.username == username))
        if check.scalar_one_or_none():
            username = f"{username}_{secrets.token_hex(3)}"

        user = User(
            id=uuid4(),
            tenant_id=tenant_id,
            username=username,
            email=email.lower(),
            full_name=full_name or username,
            password_hash=hash_password(secrets.token_urlsafe(32)),  # Random password (SSO users don't use it)
            role=mapped_role,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        logger.info(f"SSO auto-provisioned user: {username} ({email}) for tenant {tenant_id}")
    else:
        raise HTTPException(
            status_code=403,
            detail="User not found and auto-provisioning is disabled. Contact your administrator.",
        )

    # Log SSO login
    await log_audit(
        db=db,
        action=AuditAction.LOGIN,
        user_id=str(user.id),
        resource_type="user",
        resource_id=str(user.id),
        details={"method": "sso", "provider": cfg.get("provider", "oidc"), "email": email},
        request=request,
    )
    await db.commit()

    # Issue our JWT
    jwt_token = create_access_token(
        user_id=str(user.id),
        username=user.username,
        role=user.role.value if hasattr(user.role, "value") else user.role,
        tenant_id=str(user.tenant_id) if user.tenant_id else None,
        business_unit_id=str(user.business_unit_id) if user.business_unit_id else None,
    )

    # Redirect to frontend with token
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost"))
    frontend_url = f"{scheme}://{host}/login/sso-callback?token={jwt_token}"

    return RedirectResponse(url=frontend_url, status_code=302)
