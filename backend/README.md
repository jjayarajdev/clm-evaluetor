# Contract Intelligence MVP - Backend

FastAPI backend for the Contract Intelligence platform with schema-driven extraction and canonical data model.

## Setup

```bash
uv sync
uv run uvicorn app.main:app --reload
```

## API Documentation

- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc
- Health Check: http://localhost:8000/api/health

## Database Migrations

```bash
# Run migrations
uv run alembic upgrade head

# Create new migration
uv run alembic revision --autogenerate -m "description"
```

## Architecture

### Canonical Data Model

The backend uses a "super canonical" data model that is contract-type agnostic and can handle any vendor/company format:

#### Core Models
- **Contract** - Main contract entity with promoted fields for efficient querying
- **ContractParty** - Parties involved (provider, client, vendor, etc.)
- **ContractKeyDate** - Important dates with alerts (expiration, renewal, deadlines)
- **Clause** - Extracted contract clauses with risk assessment
- **Obligation** - Contractual obligations with owner, category, and compliance tracking

#### Canonical Extension Models
- **ContractFinancial** - Fee structures, payment terms, and penalties
- **ContractLiability** - Liability caps, indemnification, and insurance requirements
- **ContractClauseIndicator** - 50+ boolean flags for clause presence/absence
- **ContractLink** - Parent-child relationships (MSA → SOW, amendments, etc.)

### Schema-Driven Extraction

Contracts are processed through a hybrid approach:
1. Full extraction stored in JSONB (`schema_data` field)
2. Important fields promoted to columns for efficient querying
3. Canonical tables populated for structured analysis

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login and get JWT token
- `POST /api/auth/register` - Register new user (admin only)

### Contracts
- `POST /api/contracts/upload` - Upload single contract
- `POST /api/contracts/upload/batch` - Upload multiple contracts
- `GET /api/contracts` - List contracts with filters
- `GET /api/contracts/{id}` - Get contract details
- `POST /api/contracts/{id}/analyze` - Run AI analysis

### Dashboard Endpoints

#### Contract Cockpit
`GET /api/dashboard/cockpit/{contract_id}`

Comprehensive single-contract view including:
- Contract metadata and key terms
- Parties with roles and jurisdiction
- Key dates timeline with urgency levels
- Financial terms and penalties
- Liability caps and indemnification
- Obligations matrix (provider/client/mutual)
- Clause presence indicators
- Linked contracts (parent/child)
- Risk summary and factors

#### Obligations & Compliance
`GET /api/dashboard/obligations-compliance`

Portfolio-wide obligation tracking:
- RAG status summary (Green/Amber/Red) with compliance rate
- Overdue and critical upcoming obligations
- Breakdown by category, owner, frequency
- 30-day compliance calendar
- Contract risk exposure
- Top risk contracts

Query params: `contract_id`, `owner_filter`, `category_filter`

#### Portfolio Dashboard
`GET /api/dashboard/portfolio`

Cross-contract analytics:
- Total contracts by status and type
- Value metrics (total, by currency, by counterparty)
- Risk distribution and metrics
- Obligation compliance rates
- Clause coverage analysis
- Counterparty concentration/exposure
- Expiring contracts timeline
- System alerts

#### Role-Specific Dashboards
- `GET /api/dashboard/admin` - Admin system overview
- `GET /api/dashboard/legal` - Legal risk and compliance view
- `GET /api/dashboard/procurement` - Vendor and spend management

### Query & AI
- `POST /api/query` - Natural language contract queries
- `GET /api/schemas` - Available extraction schemas

## Data Models Reference

### Obligation Categories
```
service_provision, service_levels, delivery, performance,
payment, invoicing, pricing,
data_protection, data_handling, reporting, information_provision,
regulatory_compliance, audit, certification, insurance,
confidentiality, ip_protection,
notification, approval, cooperation,
staffing, training, documentation, maintenance, support, testing,
transition, exit_management, return_of_materials
```

### Obligation Owners
```
provider, client, mutual, third_party, unspecified
```

### RAG Status
```
green - On track, no issues
amber - At risk, attention needed
red - Overdue or breached
not_assessed - Not yet evaluated
```

### Fee Types
```
base_fee, per_unit, per_hour, per_day, percentage, milestone,
recurring_monthly, recurring_annual, one_time, retainer,
success_fee, licensing_fee, maintenance_fee, support_fee
```

### Liability Cap Types
```
none, unlimited, fixed_amount, fees_paid, annual_fees,
multiple_of_fees, percentage_of_value, insurance_limit, custom
```

### Contract Link Types
```
sow, work_order, service_order, purchase_order,
amendment, addendum, change_order, modification, renewal,
exhibit, schedule, appendix, attachment,
supersedes, references, related
```

## Environment Variables

See `.env.example` for required configuration:
- `DATABASE_URL` - PostgreSQL connection string
- `OPENAI_API_KEY` - OpenAI API key for AI extraction
- `JWT_SECRET_KEY` - Secret for JWT token signing
- `CHROMA_HOST` - ChromaDB host for vector storage

## Development

### Project Structure
```
app/
├── agents/          # AI agents for extraction
├── core/            # Auth, dependencies, middleware
├── models/          # SQLAlchemy models
├── routers/         # API endpoints
├── schemas/         # Pydantic schemas & extraction templates
├── services/        # Business logic
└── main.py          # FastAPI application
```

### Running Tests
```bash
uv run pytest
```

### Code Quality
```bash
uv run ruff check .
uv run ruff format .
```
