---
name: new-router
description: Scaffold a new FastAPI router with tenant isolation, standard CRUD endpoints, and Pydantic schemas
allowed-tools: Read, Write, Edit, Grep, Glob
---

# Scaffold New Router

Create a new FastAPI router following project conventions.

## Arguments
The user provides: resource name (e.g., "invoices")

## Steps

1. **Create the model** at `backend/app/models/{resource}.py`:
   - UUID primary key with `default=uuid.uuid4`
   - `tenant_id` foreign key to `tenants.id`
   - Standard `created_at`, `updated_at` timestamps
   - Register in `backend/app/models/__init__.py`

2. **Create the router** at `backend/app/routers/{resource}.py`:
   - Prefix: `/api/{resource}`
   - Include `apply_tenant_filter()` helper
   - Standard endpoints: GET list (paginated), GET by id, POST create, PUT update, DELETE
   - All endpoints use `CurrentTenantId` and `get_current_user` dependencies
   - Admin-only for create/update/delete using `require_role(["admin", "legal"])`

3. **Create Pydantic schemas** inline or in `backend/app/schemas/{resource}.py`:
   - `{Resource}Create` — creation schema
   - `{Resource}Update` — partial update schema (all fields optional)
   - `{Resource}Response` — response schema
   - `{Resource}ListResponse` — paginated list: `items`, `total`, `page`, `page_size`, `pages`

4. **Register the router** in `backend/app/main.py`:
   ```python
   from app.routers.{resource} import router as {resource}_router
   app.include_router({resource}_router)
   ```

5. **Create Alembic migration** if new enum types are used:
   ```python
   op.execute("ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")
   ```

## Conventions
- All routers use `/api/` prefix
- Use `PG_ENUM()` for enum columns, never `Enum()`
- Paginated responses: `{items: [], total, page, page_size, pages}`
- Super admin has `tenant_id=null` — use `CurrentTenantId` (nullable) not `RequiredTenantId`
