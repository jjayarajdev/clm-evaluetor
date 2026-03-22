# Backend CLAUDE.md

FastAPI backend with async SQLAlchemy, multi-tenant architecture, and 9 AI agents.

## Quick Reference

```bash
uv sync                                          # Install deps
uv run uvicorn app.main:app --reload              # Dev server
uv run pytest                                     # Run tests
uv run python -m scripts.seed_data                # Seed core data
uv run python -m scripts.seed_relationship_governance  # Seed governance data
```

## Code Conventions

### Router Pattern
All routers use `/api/` prefix. Standard structure:
```python
router = APIRouter(prefix="/api/resource", tags=["Resource"])

@router.get("")
async def list_resources(
    tenant_id: CurrentTenantId,              # From JWT, None for super_admin
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Model)
    query = apply_tenant_filter(query, tenant_id)  # ALWAYS filter by tenant
    ...
```

### Dependency Injection
| Dependency | Purpose |
|-----------|---------|
| `CurrentUser` | Any authenticated user |
| `AdminUser` | Admin or super_admin |
| `SuperAdminUser` | Super admin only |
| `CurrentTenantId` | UUID or None (super_admin) |
| `RequiredTenantId` | UUID, raises 403 if None |

### Model Pattern
```python
class MyModel(Base):
    __tablename__ = "my_models"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    # Use PG_ENUM for PostgreSQL enum columns:
    status = Column(
        PG_ENUM(*[e.value for e in StatusEnum], name='statusenum', create_type=False),
        nullable=False, default=StatusEnum.ACTIVE.value
    )
```

### Paginated Response Pattern
List endpoints return: `{"items": [...], "total": N, "page": 1, "page_size": 20, "pages": N}`

## Critical Pitfalls

- **Enum columns:** Use `PG_ENUM()` not `Enum()` — the latter sends uppercase names to PostgreSQL
- **Savepoints:** Never use `begin_nested()` — causes `MissingGreenlet` in async
- **Dynamic relationships:** `lazy="dynamic"` can't use `selectinload` — query separately
- **Metadata flush:** Always flush metadata before optional AI stages (risk, KG) so it survives failures
- **KG extraction:** Deferred to `_run_deep_analysis` to prevent FK violations poisoning the session
- **Currency column:** VARCHAR(3) constraint — map full names to ISO codes ("US Dollar" → "USD")
- **Contract type mapping:** Handle full names ("Master Services Agreement" → "MSA"), don't clear existing values for unrecognized types
- **Super admin tenant_id:** Is None from JWT — must accept from request body when creating resources

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app, router registration |
| `app/database.py` | Async engine, session maker |
| `app/core/deps.py` | Auth dependencies (CurrentUser, AdminUser, etc.) |
| `app/core/security.py` | JWT creation, password hashing |
| `app/services/indexer.py` | Document ingestion pipeline |
| `app/services/orchestrator.py` | Agent Squad orchestration |
| `app/services/vector_store.py` | ChromaDB operations |

## Seed Scripts

| Script | Purpose |
|--------|---------|
| `seed_data.py` | Core: tenants, users, contracts, AI processing |
| `seed_relationship_governance.py` | Governance: orgs, relationships, KPIs, scores |
| `seed_business_units.py` | Business unit hierarchy |
| `seed_compliance_rules.py` | Compliance rules |
| `seed_contract_distribution.py` | Distribute contracts across tenants |
| `clear_seed_data.py` | Reset database |
