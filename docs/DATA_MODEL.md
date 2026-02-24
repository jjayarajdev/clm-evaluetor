# CLM Platform Data Model

## Multi-Tenancy Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PLATFORM                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Super Admin Users (tenant_id = NULL)                                │   │
│  │  - Can access all tenants                                            │   │
│  │  - Platform-wide administration                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Survey Templates (platform-wide, reusable across tenants)           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         TENANT (Acme Corp)                             │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │ │
│  │  │  Custom Field Definitions (JSONB schema for this tenant)        │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                        │ │
│  │  ┌─────────────┐    ┌─────────────────┐    ┌────────────────────┐    │ │
│  │  │   Users     │    │  Organisations  │    │    Contracts       │    │ │
│  │  │  (N per     │    │  (counterparties│    │  (with files)      │    │ │
│  │  │   tenant)   │    │   & self)       │    │                    │    │ │
│  │  └─────────────┘    └─────────────────┘    └────────────────────┘    │ │
│  │         │                   │                       │                 │ │
│  │         │                   │                       │                 │ │
│  │         ▼                   ▼                       ▼                 │ │
│  │  ┌──────────────────────────────────────────────────────────────┐    │ │
│  │  │              Business Relationships                          │    │ │
│  │  │  (links Org A ↔ Org B with KPIs, Surveys, Contracts)        │    │ │
│  │  └──────────────────────────────────────────────────────────────┘    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         TENANT (TechStart)                             │ │
│  │                    (completely isolated data)                          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Entity Relationships

### Core Hierarchy

```
Platform (1)
    │
    ├── Super Admin Users (N)           [tenant_id = NULL]
    │
    ├── Survey Templates (N)            [platform-wide, reusable]
    │
    └── Tenants (N)
            │
            ├── Custom Field Definitions [JSONB schema per tenant]
            │
            ├── Users (N)                [tenant_id required]
            │       │
            │       └── uploads ──► Contracts
            │
            ├── Organisations (N)        [counterparties: vendors, clients, partners]
            │       │
            │       └── linked via ──► Business Relationships
            │
            ├── Contracts (N)            [with embedded files]
            │       │
            │       ├── Clauses (N)
            │       ├── Obligations (N)
            │       ├── SLAs (N)
            │       ├── Exhibits (N)
            │       └── custom_fields [JSONB values]
            │
            └── Business Relationships (N)
                    │
                    ├── org_a ──► Organisation
                    ├── org_b ──► Organisation
                    ├── contracts (N)
                    ├── KPIs (N)
                    │     └── Perception Scores (N)
                    ├── Improvement Points (N)
                    └── Survey Instances (N)
```

## Detailed Cardinalities

| Relationship | Cardinality | Notes |
|--------------|-------------|-------|
| Platform : Tenant | 1 : N | Platform hosts multiple tenants |
| Platform : Super Admin | 1 : N | Super admins have `tenant_id = NULL` |
| Platform : Survey Template | 1 : N | Templates reusable across tenants |
| Tenant : User | 1 : N | Each user belongs to exactly one tenant |
| Tenant : Organisation | 1 : N | Orgs are tenant-scoped counterparties |
| Tenant : Contract | 1 : N | Contracts isolated per tenant |
| Tenant : Business Relationship | 1 : N | Relationships within tenant |
| User : Contract | 1 : N | User uploads many contracts |
| Organisation : Business Relationship | N : N | Org can be in many relationships (as A or B) |
| Business Relationship : Contract | 1 : N | Relationship governs multiple contracts |
| Business Relationship : KPI | 1 : N | Relationship has many KPIs |
| KPI : Perception Score | 1 : N | Each KPI has internal & external scores |
| Contract : Clause | 1 : N | Contract has many extracted clauses |
| Contract : Obligation | 1 : N | Contract has many obligations |
| Contract : Document/File | 1 : 1 | File embedded in contract (file_path) |

## Key Questions Addressed

### 1. Where do files belong?

**Answer: Files are PER TENANT, stored with Contract**

```
Contract Model:
├── file_path      → "/data/uploads/{tenant_id}/{contract_id}.pdf"
├── filename       → "MSA-TechServices-2024.pdf"
├── file_size      → 245678
├── mime_type      → "application/pdf"
└── content_hash   → SHA256 for deduplication
```

- Files are stored on local filesystem at `data/uploads/`
- Path includes tenant isolation: `{tenant_id}/{filename}`
- No separate Document/File model - embedded in Contract
- Single file per contract (main document)
- Exhibits are text extracts, not separate files

### 2. What is Organisation's relationship to Tenant?

**Answer: Organisations are TENANT-SCOPED counterparties**

```python
class Organization(Base, TenantMixin):
    tenant_id: UUID          # Required - org belongs to this tenant
    org_type: Enum           # customer, vendor, partner, internal
    name: str
    # ... contact details
```

- Each tenant manages their own list of counterparties
- `org_type` distinguishes: `customer` (you sell to) vs `vendor` (you buy from)
- Organisations can exist without users (they're counterparties, not platform users)
- The tenant's own company can be an Organisation with `org_type = "internal"`

### 3. Can Organisation be a counterparty without Users?

**Answer: YES - Organisations don't need users**

```
Tenant (Acme Corp - has users)
    │
    ├── Organisation: "Acme Corp Internal" (type: internal)
    │       └── This is the tenant's own org record
    │
    ├── Organisation: "TechServices Inc" (type: vendor)
    │       └── No users - just a counterparty record
    │
    └── Organisation: "GlobalSupply" (type: vendor)
            └── No users - just a counterparty record
```

- Organisations are contact/counterparty records
- Users are platform login accounts
- A vendor/client org doesn't need to be a tenant or have users
- They become "known counterparties" for contract management

### 4. What is Custom Fields scope?

**Answer: Schema per TENANT, values per ENTITY**

```
Tenant.custom_field_definitions = {
    "contract": [
        {"name": "department", "type": "select", "options": ["Legal", "IT", "HR"]},
        {"name": "project_code", "type": "text"}
    ],
    "obligation": [
        {"name": "owner_email", "type": "email"}
    ]
}

Contract.custom_fields = {
    "department": "Legal",
    "project_code": "PRJ-2024-001"
}
```

| Level | Location | Purpose |
|-------|----------|---------|
| Tenant | `custom_field_definitions` (JSONB) | Schema definition |
| Contract | `custom_fields` (JSONB) | Actual values |
| Clause | `custom_fields` (JSONB) | Actual values |
| Obligation | `custom_fields` (JSONB) | Actual values |

- Each tenant defines their own field schema
- Entities store actual values in their own JSONB column
- No database migrations needed for new fields

### 5. Super Admin vs Normal User

**Answer: Super Admin has NULL tenant_id**

```python
class User(Base):
    tenant_id: UUID | None  # NULL for super_admin
    role: Enum              # super_admin, admin, legal, procurement, viewer
```

| User Type | tenant_id | Access |
|-----------|-----------|--------|
| Super Admin | NULL | All tenants, platform settings |
| Admin | UUID | Own tenant only |
| Legal | UUID | Own tenant only |
| Viewer | UUID | Own tenant only (read) |

## Visual ER Diagram

```
┌─────────────┐       ┌──────────────┐       ┌───────────────┐
│   TENANT    │       │     USER     │       │ ORGANISATION  │
├─────────────┤       ├──────────────┤       ├───────────────┤
│ id (PK)     │◄──┬───│ tenant_id(FK)│   ┌───│ tenant_id(FK) │
│ name        │   │   │ username     │   │   │ name          │
│ slug        │   │   │ email        │   │   │ org_type      │
│ plan        │   │   │ role         │   │   │ (vendor/      │
│ custom_     │   │   │ is_active    │   │   │  client/      │
│ field_defs  │   │   └──────────────┘   │   │  partner)     │
└─────────────┘   │                      │   └───────────────┘
                  │                      │          │
                  │   ┌──────────────┐   │          │
                  │   │   CONTRACT   │   │          │
                  │   ├──────────────┤   │          │
                  └───│ tenant_id(FK)│◄──┘          │
                      │ uploaded_by  │──────────────┤
                      │ filename     │              │
                      │ file_path    │              │
                      │ custom_fields│              │
                      └──────────────┘              │
                            │                       │
                            │                       │
                            ▼                       ▼
                  ┌────────────────────────────────────┐
                  │       BUSINESS_RELATIONSHIP        │
                  ├────────────────────────────────────┤
                  │ tenant_id (FK)                     │
                  │ org_a_id (FK) ──► Organisation     │
                  │ org_b_id (FK) ──► Organisation     │
                  │ relationship_type                  │
                  │ health_score                       │
                  └────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌─────────┐   ┌─────────┐   ┌──────────────┐
        │   KPI   │   │ SURVEY  │   │ IMPROVEMENT  │
        │         │   │INSTANCE │   │    POINT     │
        └─────────┘   └─────────┘   └──────────────┘
              │
              ▼
        ┌───────────────┐
        │  PERCEPTION   │
        │    SCORE      │
        └───────────────┘
```

## Summary: Reviewer's Questions Answered

| Question | Answer |
|----------|--------|
| Files per Tenant? | **Yes** - stored at `data/uploads/{tenant_id}/` |
| Files per Platform? | **No** - tenant-isolated |
| Org without Users? | **Yes** - Orgs are counterparty records, not user accounts |
| Custom Fields scope? | **Schema per Tenant, Values per Entity** |
| Super Admin scope? | **Platform-wide** (tenant_id = NULL) |
| Vendor vs Client? | **org_type enum**: vendor, customer, partner, internal |
