# Implementation Tasks: Contract Intelligence MVP

Generated from: `tasks/prd-contract-intelligence-mvp.md`
Generated on: 2025-02-01
**Updated: 2026-02-14** - Added Phase 9 (Relationship Governance) and Phase 10 (Mobile & Surveys)
Total Tasks: 54 parent tasks, ~250 sub-tasks

## Relevant Files

*Updated as implementation progresses*

### Project Structure (Created)
- `backend/` - Python FastAPI backend root
- `backend/app/` - Application code
- `backend/app/models/` - SQLAlchemy models
- `backend/app/routers/` - API route handlers
- `backend/app/services/` - Business logic services
- `backend/app/agents/` - Agent Squad agent implementations
- `backend/app/schemas/` - Pydantic schemas for request/response validation
- `backend/app/main.py` - FastAPI application entry point
- `backend/app/config.py` - Pydantic Settings configuration
- `backend/app/database.py` - Async SQLAlchemy engine and session management
- `backend/app/models/base.py` - SQLAlchemy mixins (UUID, Timestamp)
- `backend/app/models/user.py` - User model with Role enum
- `backend/app/models/contract.py` - Contract model with enums
- `backend/app/models/clause.py` - Clause model with ClauseType enum
- `backend/app/models/obligation.py` - Obligation model with enums
- `backend/app/models/audit.py` - AuditLog model with AuditAction enum
- `backend/app/models/alert.py` - AlertConfig model with AlertType enum
- `backend/app/services/vector_store.py` - ChromaDB vector store service with RBAC
- `backend/app/services/orchestrator.py` - Agent Squad orchestrator with Langfuse
- `backend/app/core/security.py` - Password hashing and JWT utilities
- `backend/app/core/deps.py` - FastAPI dependencies for auth and RBAC
- `backend/app/schemas/auth.py` - Auth request/response schemas
- `backend/app/routers/auth.py` - Auth endpoints (login, me, logout)
- `backend/scripts/seed_users.py` - Seed script for default users
- `backend/app/schemas/user.py` - User CRUD schemas
- `backend/app/services/users.py` - User service with CRUD operations
- `backend/app/routers/users.py` - User management endpoints
- `backend/app/schemas/audit.py` - Audit log schemas
- `backend/app/services/audit.py` - Audit logging service
- `backend/app/routers/audit.py` - Audit log endpoints
- `backend/app/core/audit.py` - Audit logging utilities
- `backend/app/schemas/contract.py` - Contract Pydantic schemas (upload, response, filters)
- `backend/app/services/upload.py` - File upload service (single, batch, ZIP)
- `backend/app/services/parser.py` - Document parsing service (PDF, DOCX, OCR)
- `backend/app/services/chunker.py` - Semantic chunking service
- `backend/app/services/indexer.py` - Indexing service and ingestion pipeline
- `backend/app/agents/base.py` - Base agent utilities, ContractSearchTool, and factories
- `backend/app/agents/metadata_extraction.py` - Metadata Extraction Agent (SK-001)
- `backend/app/agents/clause_extraction.py` - Clause Extraction Agent (SK-002)
- `backend/app/agents/obligation_tracking.py` - Obligation Tracking Agent (SK-003)
- `backend/app/agents/risk_detection.py` - Risk Detection Agent (SK-004)
- `backend/app/agents/renewal_monitoring.py` - Renewal Monitoring Agent (SK-005)
- `backend/app/agents/contract_qa.py` - Contract Q&A Agent (SK-006)
- `backend/app/services/contracts.py` - Contract CRUD service
- `backend/app/routers/contracts.py` - Contract upload, processing, CRUD, and search endpoints
- `backend/app/routers/query.py` - Q&A and analysis endpoints
- `backend/app/routers/dashboard.py` - Admin, Legal, and Procurement dashboard endpoints
- `backend/pyproject.toml` - Python dependencies (UV package manager)
- `frontend/` - React frontend root
- `frontend/src/` - Source code
- `frontend/src/components/` - Reusable UI components
- `frontend/src/pages/` - Page components
- `frontend/src/hooks/` - Custom React hooks
- `frontend/src/services/` - API client services
- `docker/` - Docker configuration files
- `docker-compose.yml` - Docker Compose with PostgreSQL, ChromaDB services
- `.env.example` - Environment variable template
- `.gitignore` - Git ignore rules for Python, Node, Docker
- `README.md` - Project documentation with setup instructions
- `docs/` - Documentation
- `data/uploads/` - Uploaded contract files
- `data/processed/` - Processed contract files

### Backend (Python/FastAPI)
- `backend/` - Backend root directory
- `backend/app/main.py` - FastAPI application entry point
- `backend/app/config.py` - Configuration and environment variables
- `backend/app/models/` - SQLAlchemy models
- `backend/app/routers/` - API route handlers
- `backend/app/services/` - Business logic services
- `backend/app/agents/` - Agent Squad agent implementations
- `backend/app/services/orchestrator.py` - Agent Squad orchestrator setup
- `backend/pyproject.toml` - Python dependencies (UV package manager)
- `backend/alembic/` - Database migrations
- `backend/alembic/env.py` - Async Alembic configuration
- `backend/alembic/versions/` - Migration files

### Frontend (React/TypeScript)
- `frontend/` - Frontend root directory
- `frontend/src/App.tsx` - Main React application
- `frontend/src/components/` - Reusable UI components
- `frontend/src/pages/` - Page components
- `frontend/src/hooks/` - Custom React hooks
- `frontend/src/services/` - API client services
- `frontend/package.json` - Node dependencies

### Infrastructure
- `docker-compose.yml` - Docker Compose configuration
- `.env.example` - Environment variable template
- `README.md` - Project documentation

### Notes
- Install backend deps: `cd backend && uv sync`
- Run backend tests: `cd backend && uv run pytest`
- Run frontend tests: `cd frontend && npm test`
- Start all services: `docker-compose up`

---

## Summary

This implementation follows a **backend-first** approach, building the complete API layer before the frontend. The AI/ML pipeline uses **Agent Squad** with **OpenAI GPT-4o** and **Langfuse** for observability, with 7 specialized agents implementing the core intelligence features. Email alerts are **deferred** to Phase 2.

## Critical Path

```
Phase 0-4: COMPLETE ✅
Task 1 (Docker) → Task 2 (PostgreSQL) → Task 3 (ChromaDB) → Task 4 (Agent Squad)
    ↓
Task 5 (Auth) → Task 6 (RBAC) → Task 8 (Upload) → Task 9-11 (Parsing/Indexing)
    ↓
Task 12 (Orchestrator) → Tasks 13-18 (Agents) → Tasks 19-22 (API Endpoints)

Phase 5-7: FRONTEND & INTEGRATION
    ↓
Task 23 (React) → Tasks 24-26 (Foundation) → Tasks 27-32 (Features)
    ↓
Task 33 (Docker Final) → Task 34 (Sample Data) → Task 35 (Documentation)

Phase 8: POST-SIGNING
    ↓
Tasks 36-43 (Post-Signing Management)

Phase 9-10: RELATIONSHIP GOVERNANCE & MOBILE
    ↓
Tasks 44-51 (Relationship Governance) → Tasks 52-54 (Mobile & Surveys)
```

## Phase 8 Critical Path (Post-Signing)

```
Task 36 (Compliance Workflow) → Task 37 (SLA Tracking) → Task 40 (Vendor Scoring)
    ↓
Task 38 (Renewals) + Task 39 (Amendments) → Task 41 (Milestone Dashboard)
    ↓
Task 42 (Compliance Reports) → Task 43 (Frontend Views)
```

## Phase 9-10 Critical Path (Evaluetor Features)

```
Task 44 (Relationship Model) → Task 45 (Org/Relationship APIs) → Task 46 (KPI Management)
    ↓
Task 47 (Perception Scoring) → Task 48 (Improvement Tracking)
    ↓
Task 49 (Business Leader Dashboard) + Task 50 (Account Manager Dashboard)
    ↓
Task 51 (Governance) → Task 52 (Surveys) → Task 53 (External Portal) → Task 54 (PWA)
```

---

## Phase 0: Project Setup

---

### ~~Task 1: Initialize project structure and Docker environment~~ [COMPLETED]

**Type:** Setup
**Priority:** P0-Critical
**Dependencies:** None
**PRD Reference:** Section 7.1

**Description:**
Create the monorepo project structure with separate backend and frontend directories. Set up Docker Compose with base services for development.

**Acceptance Criteria:**
- [x] Project structure created with backend/ and frontend/ directories
- [x] Docker Compose runs PostgreSQL and ChromaDB containers
- [x] Environment variable template (.env.example) created
- [x] Basic README with setup instructions

**Sub-tasks:**
- [x] 1.1 Create project root structure (backend/, frontend/, docker/, docs/)
- [x] 1.2 Create backend Python project with pyproject.toml or requirements.txt
- [x] 1.3 Create docker-compose.yml with PostgreSQL 15 service
- [x] 1.4 Add ChromaDB service to docker-compose.yml
- [x] 1.5 Create .env.example with all required environment variables
- [x] 1.6 Create .gitignore for Python, Node, and Docker artifacts
- [x] 1.7 Write initial README.md with project overview and setup steps

**Technical Notes:**
- Use Python 3.11+ for backend
- PostgreSQL 15 with pgvector extension (optional for future)
- ChromaDB latest stable version
- Mount volumes for data persistence

---

### ~~Task 2: Set up PostgreSQL database with schema and migrations~~ [COMPLETED]

**Type:** Setup
**Priority:** P0-Critical
**Dependencies:** Task 1
**PRD Reference:** FR-1.7, FR-4.1, Section 7.3

**Description:**
Configure PostgreSQL connection, set up Alembic for migrations, and create the initial database schema including users, contracts, clauses, and obligations tables.

**Acceptance Criteria:**
- [x] Database connection established from FastAPI
- [x] Alembic configured for migrations
- [x] All core tables created (users, contracts, clauses, obligations, alerts)
- [-] Migrations run successfully on fresh database (requires Docker)

**Sub-tasks:**
- [x] 2.1 Install SQLAlchemy, asyncpg, and Alembic dependencies
- [x] 2.2 Create database configuration module (app/config.py)
- [x] 2.3 Create SQLAlchemy Base and session management
- [x] 2.4 Create User model (id, username, email, password_hash, role, is_active, timestamps)
- [x] 2.5 Create Contract model (id, filename, file_path, contract_type, counterparty, dates, value, jurisdiction, risk_score, status, uploaded_by, timestamps)
- [x] 2.6 Create Clause model (id, contract_id, clause_type, text, section_number, page_number, risk_level, confidence_score, timestamps)
- [x] 2.7 Create Obligation model (id, contract_id, clause_id, description, responsible_party, deadline, status, timestamps)
- [x] 2.8 Create AuditLog model (id, user_id, action, resource, details, timestamp)
- [x] 2.9 Create AlertConfig model (id, user_id, alert_type, threshold_days, is_enabled)
- [x] 2.10 Initialize Alembic and create initial migration
- [-] 2.11 Test migration up/down on fresh database (requires Docker)

**Technical Notes:**
- Use async SQLAlchemy with asyncpg driver
- Add indexes on frequently queried columns (contract_type, counterparty, expiration_date)
- Use UUID for primary keys for better distribution

---

### ~~Task 3: Set up ChromaDB vector store~~ [COMPLETED]

**Type:** Setup
**Priority:** P0-Critical
**Dependencies:** Task 1
**PRD Reference:** FR-1.6

**Description:**
Configure ChromaDB client, create collections for contract chunks, and implement basic vector operations (add, query, delete).

**Acceptance Criteria:**
- [x] ChromaDB client connects successfully
- [x] Collection created for contract chunks
- [x] Basic CRUD operations work (add, query, delete vectors)
- [x] Metadata filtering works on queries

**Sub-tasks:**
- [x] 3.1 Install chromadb Python client
- [x] 3.2 Create ChromaDB service module (app/services/vector_store.py)
- [x] 3.3 Implement connection with configurable host/port
- [x] 3.4 Create "contract_chunks" collection with metadata schema
- [x] 3.5 Implement add_documents() method with embeddings and metadata
- [x] 3.6 Implement query_similar() method with filters and top-k
- [x] 3.7 Implement delete_by_contract_id() method for cleanup
- [x] 3.8 Add health check endpoint for ChromaDB connection
- [-] 3.9 Write unit tests for vector store operations (deferred - minimal testing)

**Technical Notes:**
- Use ChromaDB's built-in embedding function initially (can swap to OpenAI later)
- Metadata should include: contract_id, clause_type, section_number, page_number
- Configure collection with cosine similarity

---

### ~~Task 4: Configure Agent Squad with OpenAI and Langfuse~~ [COMPLETED]

**Type:** Setup
**Priority:** P0-Critical
**Dependencies:** Task 1
**PRD Reference:** FR-2.1, Section 7.1

**Description:**
Set up Agent Squad framework with OpenAI as the LLM provider and Langfuse for observability. No AWS dependencies required.

**Acceptance Criteria:**
- [x] Agent Squad installed and configured with OpenAI
- [x] Langfuse observability integrated via OpenTelemetry
- [x] Simple test agent returns valid response
- [-] Traces visible in Langfuse dashboard (requires running app)

**Sub-tasks:**
- [x] 4.1 Install agent-squad, openai, langfuse, and opentelemetry packages
- [x] 4.2 Create environment configuration for OpenAI and Langfuse keys
- [x] 4.3 Create orchestrator service (app/services/orchestrator.py)
- [x] 4.4 Configure OpenAIClassifier for intent routing
- [x] 4.5 Configure InMemoryChatStorage (swap to PostgreSQL later)
- [x] 4.6 Set up OpenTelemetry export to Langfuse
- [x] 4.7 Create simple test OpenAIAgent to verify setup
- [-] 4.8 Verify traces appear in Langfuse dashboard (requires running app)
- [x] 4.9 Add health check endpoint for OpenAI and Langfuse connectivity
- [x] 4.10 Implement rate limiting and retry logic for API calls

**Technical Notes:**
- Use OpenAI GPT-4o as default model
- No AWS credentials required
- Langfuse can be self-hosted or use cloud version
- Enable tracing with `trace=True` in orchestrator options

---

## Phase 1: Core Backend Infrastructure

---

### ~~Task 5: Implement authentication service~~ [COMPLETED]

**Type:** Backend
**Priority:** P0-Critical
**Dependencies:** Task 2
**PRD Reference:** FR-4.2, FR-4.3

**Description:**
Build the authentication service with login endpoint, JWT token generation, password hashing, and session management.

**Acceptance Criteria:**
- [x] POST /api/auth/login accepts username/password, returns JWT
- [x] Passwords are hashed with bcrypt before storage
- [x] JWT tokens include user_id, role, and expiration
- [x] Protected endpoints reject invalid/expired tokens

**Sub-tasks:**
- [x] 5.1 Install python-jose, passlib, and bcrypt packages
- [x] 5.2 Create password hashing utilities (hash, verify)
- [x] 5.3 Create JWT utilities (create_token, decode_token, verify_token)
- [x] 5.4 Create Pydantic schemas for LoginRequest and TokenResponse
- [x] 5.5 Create auth router (app/routers/auth.py)
- [x] 5.6 Implement POST /api/auth/login endpoint
- [x] 5.7 Implement GET /api/auth/me endpoint (get current user)
- [x] 5.8 Create FastAPI dependency for extracting current user from token
- [x] 5.9 Create seed script to add default admin user
- [-] 5.10 Write tests for auth endpoints (deferred - minimal testing)

**Technical Notes:**
- Use HS256 algorithm for JWT
- Token expiration: 24 hours (configurable)
- Store JWT secret in environment variable

---

### ~~Task 6: Implement user management and RBAC~~ [COMPLETED]

**Type:** Backend
**Priority:** P0-Critical
**Dependencies:** Task 5
**PRD Reference:** FR-4.1, FR-4.4, FR-4.5, FR-4.6

**Description:**
Build user management endpoints for admins and implement role-based access control with three roles: Admin, Legal, Procurement.

**Acceptance Criteria:**
- [x] Admin can create, update, and deactivate users
- [x] Role-based middleware restricts endpoint access
- [x] Legal users cannot access admin endpoints
- [x] User list endpoint with filtering by role

**Sub-tasks:**
- [x] 6.1 Create Role enum (ADMIN, LEGAL, PROCUREMENT)
- [x] 6.2 Create Pydantic schemas for UserCreate, UserUpdate, UserResponse
- [x] 6.3 Create user service (app/services/users.py) with CRUD operations
- [x] 6.4 Create users router (app/routers/users.py)
- [x] 6.5 Implement GET /api/users (list users, admin only)
- [x] 6.6 Implement POST /api/users (create user, admin only)
- [x] 6.7 Implement GET /api/users/{id} (get user details)
- [x] 6.8 Implement PUT /api/users/{id} (update user, admin only)
- [x] 6.9 Implement DELETE /api/users/{id} (deactivate user, admin only)
- [x] 6.10 Create role_required() dependency for role-based access
- [-] 6.11 Write tests for user endpoints and RBAC (deferred)

**Technical Notes:**
- Soft delete users (set is_active=False)
- Admin cannot deactivate themselves
- Return 403 Forbidden for unauthorized role access

---

### ~~Task 7: Implement audit logging service~~ [COMPLETED]

**Type:** Backend
**Priority:** P1-High
**Dependencies:** Task 6
**PRD Reference:** FR-4.7

**Description:**
Create an audit logging service that tracks user actions (login, upload, query, etc.) for security and debugging purposes.

**Acceptance Criteria:**
- [x] All significant actions are logged to audit_log table
- [x] Logs include user_id, action, resource, timestamp
- [x] Admin can view audit logs via API
- [x] Logs are created asynchronously (non-blocking)

**Sub-tasks:**
- [x] 7.1 Create AuditAction enum (LOGIN, LOGOUT, UPLOAD, QUERY, CREATE_USER, etc.)
- [x] 7.2 Create audit service (app/services/audit.py)
- [x] 7.3 Implement log_action() async method
- [x] 7.4 Create audit router (app/routers/audit.py)
- [x] 7.5 Implement GET /api/audit (list logs, admin only, with pagination)
- [x] 7.6 Add audit logging to auth endpoints (login/logout)
- [x] 7.7 Create middleware or decorator for automatic audit logging
- [-] 7.8 Write tests for audit logging (deferred)

**Technical Notes:**
- Use background tasks for non-blocking logging
- Include IP address in audit logs if available
- Implement log retention policy (configurable days)

---

## Phase 2: Document Ingestion Pipeline

---

### ~~Task 8: Implement file upload service~~ [COMPLETED]

**Type:** Backend
**Priority:** P0-Critical
**Dependencies:** Task 6
**PRD Reference:** FR-1.1, FR-1.8

**Description:**
Build the file upload service supporting single and batch PDF/DOCX uploads with progress tracking and validation.

**Acceptance Criteria:**
- [x] POST /api/contracts/upload accepts PDF and DOCX files
- [x] Batch upload accepts multiple files or ZIP archive
- [x] Files are stored locally with unique names
- [x] Upload progress is trackable for large batches

**Sub-tasks:**
- [x] 8.1 Create upload directory structure (data/uploads/, data/processed/)
- [x] 8.2 Create file validation utilities (check type, size limits)
- [x] 8.3 Create upload service (app/services/upload.py)
- [x] 8.4 Implement single file upload with unique filename generation
- [x] 8.5 Implement batch file upload endpoint
- [x] 8.6 Implement ZIP archive extraction and processing
- [x] 8.7 Create contracts router (app/routers/contracts.py)
- [x] 8.8 Implement POST /api/contracts/upload endpoint
- [x] 8.9 Create Contract record in database on upload
- [x] 8.10 Implement upload status tracking (pending, processing, completed, failed)
- [x] 8.11 Implement GET /api/contracts/upload-status/{batch_id}
- [-] 8.12 Write tests for upload endpoints (deferred - minimal testing)

**Technical Notes:**
- Max file size: 50MB per file
- Accepted types: application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document
- Generate UUID-based filenames to avoid collisions

---

### ~~Task 9: Implement document parsing and text extraction~~ [COMPLETED]

**Type:** Backend
**Priority:** P0-Critical
**Dependencies:** Task 8
**PRD Reference:** FR-1.2, FR-1.3

**Description:**
Build document parsing service that extracts text from PDFs and DOCX files, with OCR fallback for scanned documents.

**Acceptance Criteria:**
- [x] PDF text extraction works for native PDFs
- [x] DOCX text extraction preserves structure
- [x] OCR fallback works for scanned/image PDFs
- [x] Extracted text includes page numbers

**Sub-tasks:**
- [x] 9.1 Install PyMuPDF (fitz), python-docx, and pytesseract packages
- [x] 9.2 Create document parser service (app/services/parser.py)
- [x] 9.3 Implement PDF text extraction with PyMuPDF
- [x] 9.4 Implement page-by-page extraction with page numbers
- [x] 9.5 Implement OCR fallback detection (if text is empty/minimal)
- [x] 9.6 Implement OCR extraction with Tesseract
- [x] 9.7 Implement DOCX text extraction with python-docx
- [x] 9.8 Preserve paragraph and heading structure from DOCX
- [x] 9.9 Create ParsedDocument dataclass with pages, text, metadata
- [~] 9.10 Add Tesseract to Docker image (deferred to Task 33)
- [-] 9.11 Write tests for parsing different document types (deferred)

**Technical Notes:**
- Tesseract language: English only for MVP
- Handle password-protected PDFs gracefully (mark as failed)
- Extract document metadata (title, author, creation date) if available

---

### ~~Task 10: Implement semantic chunking~~ [COMPLETED]

**Type:** Backend
**Priority:** P0-Critical
**Dependencies:** Task 9
**PRD Reference:** FR-1.3

**Description:**
Build intelligent text chunking that splits documents into meaningful segments (clauses, sections) rather than arbitrary character limits.

**Acceptance Criteria:**
- [x] Documents are chunked by logical sections/clauses
- [x] Each chunk has section number and page reference
- [x] Chunks are appropriately sized for embedding (500-1500 tokens)
- [x] Overlapping context preserved between chunks

**Sub-tasks:**
- [x] 10.1 Create chunking service (app/services/chunker.py)
- [x] 10.2 Implement section header detection (numbered sections, articles)
- [x] 10.3 Implement clause boundary detection using patterns
- [x] 10.4 Implement recursive chunking for large sections
- [x] 10.5 Add overlap between chunks (100-200 tokens)
- [x] 10.6 Create Chunk dataclass (text, section_number, page_start, page_end, char_start, char_end)
- [x] 10.7 Implement token counting for chunk size validation
- [x] 10.8 Handle edge cases (no clear sections, single page docs)
- [-] 10.9 Write tests for chunking with sample contracts (deferred)

**Technical Notes:**
- Target chunk size: 500-1000 tokens (configurable)
- Max chunk size: 1500 tokens
- Overlap: 100 tokens between chunks
- Use regex patterns for common contract section numbering (1., 1.1, Article I, Section A)

---

### ~~Task 11: Implement vector indexing and metadata storage~~ [COMPLETED]

**Type:** Backend
**Priority:** P0-Critical
**Dependencies:** Task 3, Task 10
**PRD Reference:** FR-1.6, FR-1.7

**Description:**
Build the indexing pipeline that stores document chunks in ChromaDB with embeddings and saves structured metadata to PostgreSQL.

**Acceptance Criteria:**
- [x] Chunks are embedded and stored in ChromaDB
- [x] Chunk metadata stored in PostgreSQL (clauses table)
- [x] Contract record updated with processing status
- [x] Cleanup on re-processing (delete old chunks)

**Sub-tasks:**
- [x] 11.1 Create indexing service (app/services/indexer.py)
- [x] 11.2 Implement embedding generation for chunks
- [x] 11.3 Implement batch vector insertion to ChromaDB
- [x] 11.4 Store chunk metadata in clauses table
- [x] 11.5 Link clauses to contracts via foreign key
- [x] 11.6 Update contract status on successful indexing
- [x] 11.7 Implement cleanup for re-processing (delete old vectors and clauses)
- [x] 11.8 Create ingestion orchestrator that chains: parse → chunk → index
- [x] 11.9 Implement async processing with background tasks
- [x] 11.10 Add error handling and failed document marking
- [-] 11.11 Write integration tests for full ingestion pipeline (deferred)

**Technical Notes:**
- Use OpenAI text-embedding-ada-002 for embeddings (or ChromaDB default)
- Batch size for vector insertion: 100 chunks
- Store embedding model version in metadata for future compatibility

---

## Phase 3: AI Skills Implementation

---

### ~~Task 12: Implement Agent Squad orchestrator and agent registry~~ [COMPLETED]

**Type:** AI/ML
**Priority:** P0-Critical
**Dependencies:** Task 4, Task 11
**PRD Reference:** FR-2.1, FR-2.2

**Description:**
Create the Agent Squad orchestrator with intelligent routing, agent registry, and integration with ChromaDB for context retrieval.

**Acceptance Criteria:**
- [x] Orchestrator routes queries to appropriate agents
- [x] Agents receive context from ChromaDB retrieval
- [x] Responses include confidence scores and sources
- [x] All agent calls traced in Langfuse

**Sub-tasks:**
- [x] 12.1 Create agents module (app/agents/__init__.py)
- [x] 12.2 Create base agent factory function for consistent configuration
- [x] 12.3 Configure AgentSquad orchestrator with all agents
- [x] 12.4 Implement ContractSearchTool for ChromaDB retrieval
- [x] 12.5 Implement context injection before agent execution
- [x] 12.6 Create AgentRequest and AgentResponse Pydantic models
- [x] 12.7 Implement confidence score extraction from agent outputs
- [~] 12.8 Add SupervisorAgent for complex multi-agent queries (deferred - simple routing sufficient for MVP)
- [x] 12.9 Implement agent execution logging via Langfuse
- [-] 12.10 Write tests for orchestrator with mock agents (deferred)

**Technical Notes:**
- Agents are added via orchestrator.add_agent()
- Use OpenAIClassifier for intent routing
- Default retrieval: top 10 relevant chunks
- Enable parallel_processing for independent agent tasks

---

### ~~Task 13: Implement Metadata Extraction Agent (SK-001)~~ [COMPLETED]

**Type:** AI/ML
**Priority:** P0-Critical
**Dependencies:** Task 12
**PRD Reference:** FR-3.5, FR-1.4, FR-1.5

**Description:**
Implement the Metadata Extraction Agent using OpenAIAgent that extracts structured contract attributes (type, parties, dates, value, jurisdiction) from uploaded documents.

**Acceptance Criteria:**
- [x] Agent extracts contract_type with 6 supported types
- [x] Agent extracts counterparty name
- [x] Agent extracts effective_date and expiration_date
- [x] Agent extracts contract_value and jurisdiction
- [x] Confidence scores provided for each field

**Sub-tasks:**
- [x] 13.1 Create metadata_extraction_agent (app/agents/metadata_extraction.py)
- [x] 13.2 Define OpenAIAgentOptions with extraction-focused description
- [x] 13.3 Create Pydantic output schema (MetadataOutput)
- [x] 13.4 Configure tool_config for structured JSON output
- [x] 13.5 Implement date parsing to ISO format
- [x] 13.6 Implement value extraction with currency detection
- [x] 13.7 Implement jurisdiction extraction
- [x] 13.8 Calculate per-field confidence scores
- [x] 13.9 Store extracted metadata in contracts table
- [x] 13.10 Register agent with orchestrator
- [~] 13.11 Integrate with ingestion pipeline (auto-run on upload) (wired in but needs testing)
- [-] 13.12 Write tests with sample contracts (deferred)

**Technical Notes:**
- Contract types: NDA, MSA, SOW, Amendment, Vendor Agreement, Employment Contract
- Use low temperature (0.1) for consistent extraction
- Confidence threshold: 0.7 (flag low confidence for review)

---

### ~~Task 14: Implement Clause Extraction Agent (SK-002)~~ [COMPLETED]

**Type:** AI/ML
**Priority:** P0-Critical
**Dependencies:** Task 12
**PRD Reference:** FR-3.1

**Description:**
Implement the Clause Extraction Agent using OpenAIAgent that identifies and extracts specific clause types (indemnification, termination, liability, etc.) from contracts.

**Acceptance Criteria:**
- [x] Agent extracts 17 supported clause types
- [x] Extracted clauses include exact text and section reference
- [x] Missing clauses are identified
- [x] Confidence scores provided per clause

**Sub-tasks:**
- [x] 14.1 Create clause_extraction_agent (app/agents/clause_extraction.py)
- [x] 14.2 Define OpenAIAgentOptions with clause types in description
- [x] 14.3 Create SUPPORTED_CLAUSE_TYPES constant
- [x] 14.4 Extract exact clause text with boundaries
- [x] 14.5 Extract section numbers and page references
- [x] 14.6 Identify and report missing expected clauses
- [x] 14.7 Extract sub-clause values (e.g., liability cap amount)
- [x] 14.8 Store extracted clauses in clauses table
- [x] 14.9 Register agent with orchestrator
- [-] 14.10 Write tests for clause extraction (deferred)

**Technical Notes:**
- Clause types: indemnification, limitation_of_liability, termination, confidentiality, intellectual_property, payment_terms, warranty, force_majeure, non_compete, non_solicitation, data_protection, dispute_resolution, assignment, notice, governing_law, sla, auto_renewal
- Run after metadata extraction in pipeline

---

### ~~Task 15: Implement Obligation Tracking Agent (SK-003)~~ [COMPLETED]

**Type:** AI/ML
**Priority:** P1-High
**Dependencies:** Task 12
**PRD Reference:** FR-3.2

**Description:**
Implement the Obligation Tracking Agent using OpenAIAgent that extracts contractual obligations with responsible parties, deadlines, and conditions.

**Acceptance Criteria:**
- [x] Agent extracts obligations with descriptions
- [x] Each obligation has responsible party identified
- [x] Deadlines are parsed (fixed, recurring, relative)
- [x] Obligations stored in obligations table

**Sub-tasks:**
- [x] 15.1 Create obligation_tracking_agent (app/agents/obligation_tracking.py)
- [x] 15.2 Define OpenAIAgentOptions with obligation extraction focus
- [x] 15.3 Implement obligation identification from text
- [x] 15.4 Extract obligated party and beneficiary party
- [x] 15.5 Classify obligation type (Payment, Delivery, Reporting, etc.)
- [x] 15.6 Extract and parse deadlines (fixed, recurring, relative)
- [x] 15.7 Extract triggering conditions
- [x] 15.8 Extract consequences of non-compliance
- [x] 15.9 Store obligations in obligations table
- [x] 15.10 Register agent with orchestrator
- [-] 15.11 Write tests for obligation extraction (deferred)

**Technical Notes:**
- Obligation types: Payment, Delivery, Reporting, Compliance, Notification, Other
- Deadline types: Fixed Date, Recurring, Relative, Ongoing
- Parse relative deadlines (e.g., "within 30 days of execution")

---

### ~~Task 16: Implement Risk Detection Agent (SK-004)~~ [COMPLETED]

**Type:** AI/ML
**Priority:** P0-Critical
**Dependencies:** Task 14
**PRD Reference:** FR-3.3

**Description:**
Implement the Risk Detection Agent using OpenAIAgent that identifies high-risk clauses and assigns risk scores to contracts.

**Acceptance Criteria:**
- [x] Agent detects 10 risk categories
- [x] Overall risk score (0-100) calculated
- [x] Risk level assigned (Low/Medium/High/Critical)
- [x] Recommendations provided for each risk

**Sub-tasks:**
- [x] 16.1 Create risk_detection_agent (app/agents/risk_detection.py)
- [x] 16.2 Define OpenAIAgentOptions with risk categories in description
- [x] 16.3 Create RISK_CATEGORIES constant
- [x] 16.4 Calculate severity per risk factor
- [x] 16.5 Calculate overall risk score (weighted average)
- [x] 16.6 Determine risk level from score thresholds
- [x] 16.7 Generate plain-language risk descriptions
- [x] 16.8 Generate recommendations for each risk
- [x] 16.9 Update contract risk_score in database
- [x] 16.10 Register agent with orchestrator
- [-] 16.11 Write tests for risk detection (deferred)

**Technical Notes:**
- Risk categories: unlimited_liability, broad_indemnification, weak_termination, auto_renewal_trap, unfavorable_ip, weak_confidentiality, missing_limitation, one_sided_terms, regulatory_risk, ambiguous_language
- Score thresholds: Low (0-25), Medium (26-50), High (51-75), Critical (76-100)
- Confidence threshold: 0.8

---

### ~~Task 17: Implement Renewal Monitoring Agent (SK-005)~~ [COMPLETED]

**Type:** AI/ML
**Priority:** P1-High
**Dependencies:** Task 12
**PRD Reference:** FR-3.4

**Description:**
Implement the Renewal Monitoring Agent using OpenAIAgent that extracts renewal terms, auto-renewal flags, and calculates notice period deadlines.

**Acceptance Criteria:**
- [x] Agent detects auto-renewal clauses
- [x] Notice periods extracted and deadlines calculated
- [x] Expiration dates validated/updated
- [~] Alerts generated for upcoming deadlines (urgency levels calculated, alerts deferred to Phase 2)

**Sub-tasks:**
- [x] 17.1 Create renewal_monitoring_agent (app/agents/renewal_monitoring.py)
- [x] 17.2 Define OpenAIAgentOptions with renewal extraction focus
- [x] 17.3 Detect auto-renewal presence and terms
- [x] 17.4 Extract renewal term duration
- [x] 17.5 Extract notice period (days before expiration)
- [x] 17.6 Calculate notice deadline from expiration date
- [x] 17.7 Detect termination for convenience clauses
- [x] 17.8 Update contract with renewal metadata
- [x] 17.9 Register agent with orchestrator
- [-] 17.10 Write tests for renewal monitoring (deferred)

**Technical Notes:**
- Calculate days_remaining based on current date
- Urgency levels: Immediate (<7 days), Soon (7-30 days), Upcoming (30-90 days), Future (>90 days)

---

### ~~Task 18: Implement Contract Q&A Agent with RAG (SK-006)~~ [COMPLETED]

**Type:** AI/ML
**Priority:** P0-Critical
**Dependencies:** Task 12
**PRD Reference:** FR-3.6, FR-2.3, FR-2.4, FR-2.5, FR-2.6

**Description:**
Implement the Contract Q&A Agent using OpenAIAgent with the ContractSearchTool for RAG-based question answering with source citations.

**Acceptance Criteria:**
- [x] Agent accepts natural language questions
- [x] Answers include source clause citations
- [x] Conversation context maintained for follow-ups
- [x] Suggested follow-up questions generated

**Sub-tasks:**
- [x] 18.1 Create contract_qa_agent (app/agents/contract_qa.py)
- [x] 18.2 Define OpenAIAgentOptions with Q&A focus (streaming enabled)
- [x] 18.3 Create ContractSearchTool class for ChromaDB retrieval
- [x] 18.4 Attach ContractSearchTool to agent
- [x] 18.5 Implement answer generation with citations
- [x] 18.6 Extract source references (contract, section, page)
- [x] 18.7 Configure conversation history in orchestrator storage
- [x] 18.8 Generate follow-up question suggestions
- [x] 18.9 Implement clarification detection (ambiguous questions)
- [x] 18.10 Create query router (app/routers/query.py)
- [x] 18.11 Implement POST /api/query endpoint (uses orchestrator.route_request)
- [-] 18.12 Write tests for Q&A with sample questions (deferred)

**Technical Notes:**
- Retrieve top 10 chunks, re-rank for relevance
- Include contract_id filter for scoped queries
- Use streaming=True for better UX
- Maintain conversation history via orchestrator storage

---

## Phase 4: Backend API Endpoints

---

### ~~Task 19: Implement contract CRUD and search endpoints~~ [COMPLETED]

**Type:** Backend
**Priority:** P0-Critical
**Dependencies:** Task 11
**PRD Reference:** Section 7.5

**Description:**
Build REST API endpoints for contract management: list, get details, search, and delete contracts.

**Acceptance Criteria:**
- [x] GET /api/contracts returns paginated list with filters
- [x] GET /api/contracts/{id} returns full contract details
- [x] DELETE /api/contracts/{id} removes contract and chunks
- [x] Search supports text and metadata filters

**Sub-tasks:**
- [x] 19.1 Create ContractResponse Pydantic schema
- [x] 19.2 Create ContractListResponse with pagination
- [x] 19.3 Implement GET /api/contracts with pagination
- [x] 19.4 Add filters: contract_type, counterparty, date range, risk_level
- [x] 19.5 Add sorting: by date, by risk_score, by name
- [x] 19.6 Implement GET /api/contracts/{id} with full details
- [x] 19.7 Include extracted clauses and obligations in response
- [x] 19.8 Implement DELETE /api/contracts/{id}
- [x] 19.9 Delete associated vectors from ChromaDB on delete
- [x] 19.10 Implement GET /api/contracts/search with text query
- [-] 19.11 Write tests for contract endpoints (deferred)

**Technical Notes:**
- Pagination: limit/offset with default 20, max 100
- Include clause_count, obligation_count in list response
- Audit log all delete operations

---

### ~~Task 20: Implement Admin dashboard data endpoints~~ [COMPLETED]

**Type:** Backend
**Priority:** P1-High
**Dependencies:** Task 19
**PRD Reference:** FR-5.1, FR-5.2, FR-5.3, FR-5.4, FR-5.5

**Description:**
Build API endpoints that provide data for the Admin dashboard widgets: contract stats, user stats, system activity.

**Acceptance Criteria:**
- [x] GET /api/dashboard/admin returns all admin widget data
- [x] Contract counts by type and status provided
- [x] User counts by role provided
- [x] Recent activity metrics included

**Sub-tasks:**
- [x] 20.1 Create AdminDashboardResponse Pydantic schema
- [x] 20.2 Create dashboard router (app/routers/dashboard.py)
- [x] 20.3 Implement contract stats query (count by type, by status)
- [x] 20.4 Implement user stats query (count by role, active/inactive)
- [x] 20.5 Implement activity metrics (queries last 7/30 days)
- [x] 20.6 Implement upload metrics (documents last 7/30 days)
- [x] 20.7 Implement ingestion queue status (pending, processing, failed)
- [x] 20.8 Implement GET /api/dashboard/admin endpoint
- [x] 20.9 Add role check (admin only)
- [-] 20.10 Write tests for admin dashboard endpoint (deferred)

**Technical Notes:**
- Cache dashboard data for 5 minutes (reduce DB load)
- Return recent failures with error messages

---

### ~~Task 21: Implement Legal dashboard data endpoints~~ [COMPLETED]

**Type:** Backend
**Priority:** P0-Critical
**Dependencies:** Task 16, Task 17
**PRD Reference:** FR-5.6, FR-5.7, FR-5.8, FR-5.9, FR-5.10, FR-5.11

**Description:**
Build API endpoints for Legal dashboard: risk overview, expirations, high-risk clauses, deviations.

**Acceptance Criteria:**
- [x] GET /api/dashboard/legal returns all legal widget data
- [x] Contracts ranked by risk score
- [x] Expiration timeline data provided
- [x] High-risk clauses listed with contract links

**Sub-tasks:**
- [x] 21.1 Create LegalDashboardResponse Pydantic schema
- [x] 21.2 Create widget sub-schemas (RiskOverview, ExpirationTimeline, etc.)
- [x] 21.3 Implement risk overview query (contracts by risk level)
- [x] 21.4 Implement expiration timeline query (30/60/90 days)
- [x] 21.5 Implement high-risk clauses query (top 20 flagged)
- [~] 21.6 Implement deviation alerts query (deferred - requires playbooks)
- [x] 21.7 Implement recent activity query (user's searches, views)
- [x] 21.8 Implement GET /api/dashboard/legal endpoint
- [x] 21.9 Add role check (admin or legal)
- [-] 21.10 Write tests for legal dashboard endpoint (deferred)

**Technical Notes:**
- Sort expirations by date ascending
- Include contract_id and name in all widget items for linking
- Recent activity: last 10 items

---

### ~~Task 22: Implement Procurement dashboard data endpoints~~ [COMPLETED]

**Type:** Backend
**Priority:** P0-Critical
**Dependencies:** Task 15, Task 17
**PRD Reference:** FR-5.12, FR-5.13, FR-5.14, FR-5.15, FR-5.16, FR-5.17

**Description:**
Build API endpoints for Procurement dashboard: spend commitments, vendor obligations, SLAs, auto-renewals.

**Acceptance Criteria:**
- [x] GET /api/dashboard/procurement returns all procurement widget data
- [x] Spend commitments aggregated by vendor
- [x] Upcoming obligations with deadlines
- [x] Auto-renewal risks with notice deadlines

**Sub-tasks:**
- [x] 22.1 Create ProcurementDashboardResponse Pydantic schema
- [x] 22.2 Create widget sub-schemas (SpendCommitment, VendorObligation, etc.)
- [x] 22.3 Implement spend commitments query (sum by counterparty)
- [x] 22.4 Implement vendor obligations query (next 30 days)
- [~] 22.5 Implement SLA tracker query (basic - full SLA tracking in Phase 2)
- [x] 22.6 Implement auto-renewal risks query (notice periods)
- [x] 22.7 Implement vendor summary query (contracts per vendor)
- [x] 22.8 Implement GET /api/dashboard/procurement endpoint
- [x] 22.9 Add role check (admin or procurement)
- [~] 22.10 Implement GET /api/vendors endpoint (deferred - vendor summary included in dashboard)
- [-] 22.11 Write tests for procurement dashboard endpoint (deferred)

**Technical Notes:**
- Aggregate spend by counterparty name (normalize names)
- SLA compliance: compare deadlines to current date
- Return currency with spend amounts

---

## Phase 5: Frontend Foundation

---

### Task 23: Initialize React app with TypeScript and dependencies

**Type:** Frontend
**Priority:** P0-Critical
**Dependencies:** Task 1
**PRD Reference:** Section 7.1

**Description:**
Set up the React frontend project with TypeScript, required dependencies, and development configuration.

**Acceptance Criteria:**
- [ ] React app created with TypeScript
- [ ] All UI dependencies installed
- [ ] Development server runs successfully
- [ ] Production build works

**Sub-tasks:**
- [ ] 23.1 Initialize React app with Vite and TypeScript template
- [ ] 23.2 Install React Router for navigation
- [ ] 23.3 Install Tailwind CSS for styling
- [ ] 23.4 Install Headless UI or Radix for accessible components
- [ ] 23.5 Install Axios or React Query for API calls
- [ ] 23.6 Install date-fns for date formatting
- [ ] 23.7 Install React Hook Form for form handling
- [ ] 23.8 Configure Tailwind with custom color scheme (from PRD 6.3)
- [ ] 23.9 Set up path aliases (@/components, @/hooks, etc.)
- [ ] 23.10 Create .env.local with API base URL
- [ ] 23.11 Add frontend service to docker-compose.yml

**Technical Notes:**
- Use Vite for faster development
- Tailwind CSS for utility-first styling
- React Query for server state management

---

### Task 24: Implement app layout, routing, and navigation

**Type:** Frontend
**Priority:** P0-Critical
**Dependencies:** Task 23
**PRD Reference:** Section 6.2

**Description:**
Build the main application layout with sidebar navigation, header, and routing for all main pages.

**Acceptance Criteria:**
- [ ] Sidebar navigation with role-based menu items
- [ ] Routes defined for all main pages
- [ ] Protected routes redirect to login
- [ ] Layout is responsive

**Sub-tasks:**
- [ ] 24.1 Create MainLayout component with sidebar and content area
- [ ] 24.2 Create Sidebar component with navigation links
- [ ] 24.3 Create Header component with user menu
- [ ] 24.4 Implement role-based navigation (show/hide menu items)
- [ ] 24.5 Set up React Router with routes for: login, dashboard, contracts, settings
- [ ] 24.6 Create ProtectedRoute wrapper component
- [ ] 24.7 Create placeholder page components for each route
- [ ] 24.8 Implement responsive sidebar (collapse on mobile)
- [ ] 24.9 Add breadcrumb navigation
- [ ] 24.10 Write tests for routing

**Technical Notes:**
- Sidebar width: 256px desktop, slide-out on mobile
- Use React Router v6 with nested routes
- Store current route in URL for bookmarking

---

### Task 25: Implement authentication UI

**Type:** Frontend
**Priority:** P0-Critical
**Dependencies:** Task 5, Task 24
**PRD Reference:** US-A1

**Description:**
Build the login page and authentication state management with token storage and auto-logout.

**Acceptance Criteria:**
- [ ] Login page with username/password form
- [ ] JWT token stored securely
- [ ] Auto-redirect after login based on role
- [ ] Logout clears session and redirects

**Sub-tasks:**
- [ ] 25.1 Create AuthContext for global auth state
- [ ] 25.2 Create useAuth hook for components
- [ ] 25.3 Create API client with auth interceptor
- [ ] 25.4 Implement token storage (localStorage or cookie)
- [ ] 25.5 Create LoginPage component with form
- [ ] 25.6 Implement login API call and error handling
- [ ] 25.7 Implement role-based redirect after login
- [ ] 25.8 Implement logout functionality
- [ ] 25.9 Add token refresh or expiration handling
- [ ] 25.10 Display current user in header
- [ ] 25.11 Write tests for auth flow

**Technical Notes:**
- Store token in localStorage (httpOnly cookie is better but more complex)
- Redirect: Admin → /admin, Legal → /legal, Procurement → /procurement
- Show loading state during auth check

---

### Task 26: Implement shared UI components

**Type:** Frontend
**Priority:** P1-High
**Dependencies:** Task 23
**PRD Reference:** Section 6.2, 6.3

**Description:**
Build reusable UI components: tables, badges, cards, modals, and loading states following the design system.

**Acceptance Criteria:**
- [ ] DataTable component with sorting and pagination
- [ ] Badge component with risk color variants
- [ ] Card component for dashboard widgets
- [ ] Modal component for dialogs
- [ ] Loading and empty states

**Sub-tasks:**
- [ ] 26.1 Create Badge component with variants (success, warning, error, neutral)
- [ ] 26.2 Create RiskBadge component with color coding from PRD
- [ ] 26.3 Create Card component with header, body, and actions
- [ ] 26.4 Create DataTable component with columns config
- [ ] 26.5 Add sorting functionality to DataTable
- [ ] 26.6 Add pagination controls to DataTable
- [ ] 26.7 Create Modal component with Headless UI Dialog
- [ ] 26.8 Create ConfirmDialog component for deletions
- [ ] 26.9 Create LoadingSpinner component
- [ ] 26.10 Create EmptyState component with icon and message
- [ ] 26.11 Create ErrorState component for API failures
- [ ] 26.12 Document components with Storybook (optional)

**Technical Notes:**
- Colors from PRD: High Risk (#DC2626), Medium (#F59E0B), Low (#10B981), Neutral (#6B7280)
- Table should handle 100+ rows with virtual scrolling if needed
- Modals should trap focus for accessibility

---

## Phase 6: Frontend Features

---

### Task 27: Implement contract upload UI with progress tracking

**Type:** Frontend
**Priority:** P0-Critical
**Dependencies:** Task 8, Task 26
**PRD Reference:** US-A4, FR-1.8

**Description:**
Build the contract upload interface with drag-and-drop, batch upload support, and real-time progress tracking.

**Acceptance Criteria:**
- [ ] Drag-and-drop zone for file upload
- [ ] Batch upload with file list preview
- [ ] Progress bar during upload
- [ ] Success/failure status per file

**Sub-tasks:**
- [ ] 27.1 Create UploadPage component
- [ ] 27.2 Create DropZone component with drag-and-drop
- [ ] 27.3 Display file preview list before upload
- [ ] 27.4 Implement upload API call with progress tracking
- [ ] 27.5 Create UploadProgress component with per-file status
- [ ] 27.6 Show processing status after upload (parsing, indexing)
- [ ] 27.7 Display success/failure summary after batch
- [ ] 27.8 Allow retry of failed uploads
- [ ] 27.9 Add file type validation (PDF, DOCX only)
- [ ] 27.10 Add file size validation with error message
- [ ] 27.11 Write tests for upload UI

**Technical Notes:**
- Use react-dropzone for drag-and-drop
- Show individual progress bars for batch uploads
- Poll for processing status after upload completes

---

### Task 28: Implement contract list and viewer

**Type:** Frontend
**Priority:** P0-Critical
**Dependencies:** Task 19, Task 26
**PRD Reference:** FR-7.1, FR-7.2, FR-7.3, FR-7.4, FR-7.5, FR-7.6

**Description:**
Build the contract list page with filters and the detailed contract viewer with metadata sidebar and clause highlighting.

**Acceptance Criteria:**
- [ ] Contract list with sortable columns
- [ ] Filters for type, counterparty, date, risk
- [ ] Contract viewer with document preview
- [ ] Metadata sidebar with extracted data
- [ ] Risk indicators on flagged clauses

**Sub-tasks:**
- [ ] 28.1 Create ContractListPage component
- [ ] 28.2 Implement contract table with DataTable
- [ ] 28.3 Add filter panel (contract type, risk level, date range)
- [ ] 28.4 Implement search input for text search
- [ ] 28.5 Create ContractViewerPage component
- [ ] 28.6 Create DocumentPreview component (display text or PDF)
- [ ] 28.7 Create MetadataSidebar component with extracted fields
- [ ] 28.8 Create ClauseList component with clause type badges
- [ ] 28.9 Implement clause highlighting on click
- [ ] 28.10 Add risk indicators (badges) on high-risk clauses
- [ ] 28.11 Implement download original document button
- [ ] 28.12 Write tests for contract list and viewer

**Technical Notes:**
- Use PDF.js for PDF rendering or display extracted text
- Highlight clause text with scroll-to functionality
- Sidebar shows: type, counterparty, dates, value, risk score, parties

---

### Task 29: Implement Admin dashboard with widgets

**Type:** Frontend
**Priority:** P1-High
**Dependencies:** Task 20, Task 26
**PRD Reference:** FR-5.1, FR-5.2, FR-5.3, FR-5.4, FR-5.5, US-A3

**Description:**
Build the Admin dashboard page with widgets for contract stats, user stats, activity metrics, and quick actions.

**Acceptance Criteria:**
- [ ] Contract stats widget (by type, by status)
- [ ] User stats widget (by role)
- [ ] Activity metrics widget (queries, uploads)
- [ ] Quick action buttons (add user, upload, settings)

**Sub-tasks:**
- [ ] 29.1 Create AdminDashboardPage component
- [ ] 29.2 Create DashboardGrid layout component
- [ ] 29.3 Create ContractStatsWidget (pie chart or cards)
- [ ] 29.4 Create UserStatsWidget (role breakdown)
- [ ] 29.5 Create ActivityWidget (queries, uploads over time)
- [ ] 29.6 Create IngestionQueueWidget (pending, processing, failed)
- [ ] 29.7 Create QuickActionsWidget with buttons
- [ ] 29.8 Implement API call to fetch dashboard data
- [ ] 29.9 Add loading states for each widget
- [ ] 29.10 Add refresh button for dashboard data
- [ ] 29.11 Write tests for admin dashboard

**Technical Notes:**
- Use Recharts or Chart.js for visualizations
- Widgets should be Cards with consistent styling
- Grid: 3 columns on desktop, 1 on mobile

---

### Task 30: Implement Legal dashboard with widgets

**Type:** Frontend
**Priority:** P0-Critical
**Dependencies:** Task 21, Task 26
**PRD Reference:** FR-5.6, FR-5.7, FR-5.8, FR-5.9, FR-5.10, FR-5.11, US-L1-L5

**Description:**
Build the Legal dashboard with risk overview, expiration timeline, high-risk clauses, and deviation alerts.

**Acceptance Criteria:**
- [ ] Risk overview widget with contract risk ranking
- [ ] Expiration timeline widget (30/60/90 days)
- [ ] High-risk clauses widget with links
- [ ] Embedded Q&A chat widget

**Sub-tasks:**
- [ ] 30.1 Create LegalDashboardPage component
- [ ] 30.2 Create RiskOverviewWidget (contracts by risk level)
- [ ] 30.3 Add click-through to contract from risk list
- [ ] 30.4 Create ExpirationTimelineWidget (calendar or list view)
- [ ] 30.5 Add toggle for 30/60/90 day views
- [ ] 30.6 Create HighRiskClausesWidget with clause type badges
- [ ] 30.7 Create DeviationAlertsWidget (non-standard contracts)
- [ ] 30.8 Create RecentActivityWidget (recent searches, views)
- [ ] 30.9 Embed ChatWidget for Q&A (placeholder, Task 32)
- [ ] 30.10 Implement API call to fetch legal dashboard data
- [ ] 30.11 Write tests for legal dashboard

**Technical Notes:**
- Risk overview: color-coded bars or donut chart
- Expiration: sort by date, show days remaining
- High-risk clauses: show top 10 with severity

---

### Task 31: Implement Procurement dashboard with widgets

**Type:** Frontend
**Priority:** P0-Critical
**Dependencies:** Task 22, Task 26
**PRD Reference:** FR-5.12, FR-5.13, FR-5.14, FR-5.15, FR-5.16, FR-5.17, US-P1-P5

**Description:**
Build the Procurement dashboard with spend commitments, vendor obligations, SLA tracker, and auto-renewal risks.

**Acceptance Criteria:**
- [ ] Spend commitments widget by vendor
- [ ] Vendor obligations widget with deadlines
- [ ] SLA tracker widget with compliance status
- [ ] Auto-renewal risks widget with countdown

**Sub-tasks:**
- [ ] 31.1 Create ProcurementDashboardPage component
- [ ] 31.2 Create SpendCommitmentsWidget (table or bar chart)
- [ ] 31.3 Add sorting by spend amount
- [ ] 31.4 Create VendorObligationsWidget with timeline
- [ ] 31.5 Show obligation status (pending, overdue, completed)
- [ ] 31.6 Create SLATrackerWidget with compliance indicators
- [ ] 31.7 Create AutoRenewalWidget with notice period countdown
- [ ] 31.8 Create VendorSummaryWidget (click vendor for details)
- [ ] 31.9 Embed ChatWidget for Q&A (placeholder, Task 32)
- [ ] 31.10 Implement API call to fetch procurement dashboard data
- [ ] 31.11 Write tests for procurement dashboard

**Technical Notes:**
- Spend: show currency with proper formatting
- Obligations: color by urgency (red for overdue)
- Auto-renewal: countdown in days, highlight <30 days

---

### Task 32: Implement Q&A chat interface

**Type:** Frontend
**Priority:** P0-Critical
**Dependencies:** Task 18, Task 26
**PRD Reference:** FR-5.10, FR-5.16, US-L2, US-P5

**Description:**
Build the natural language Q&A chat interface with message history, source citations, and follow-up suggestions.

**Acceptance Criteria:**
- [ ] Chat input for natural language questions
- [ ] Message history with user and assistant messages
- [ ] Source citations with links to clauses
- [ ] Suggested follow-up questions

**Sub-tasks:**
- [ ] 32.1 Create ChatWidget component (embeddable)
- [ ] 32.2 Create ChatMessage component (user/assistant variants)
- [ ] 32.3 Create ChatInput component with send button
- [ ] 32.4 Implement message state management
- [ ] 32.5 Implement query API call
- [ ] 32.6 Display loading state during query
- [ ] 32.7 Create SourceCitation component with contract link
- [ ] 32.8 Display confidence score with badge
- [ ] 32.9 Create FollowUpSuggestions component
- [ ] 32.10 Handle clarification prompts from API
- [ ] 32.11 Create full-page ChatPage for dedicated Q&A
- [ ] 32.12 Write tests for chat interface

**Technical Notes:**
- Chat widget: floating or sidebar embed
- Stream responses if API supports it (optional)
- Maintain conversation context (last 5 turns)

---

## Phase 7: Integration & Delivery

---

### Task 33: Finalize Docker Compose with all services

**Type:** Integration
**Priority:** P0-Critical
**Dependencies:** All previous tasks
**PRD Reference:** Section 7.1

**Description:**
Complete the Docker Compose configuration with all services properly configured, health checks, and single-command startup.

**Acceptance Criteria:**
- [ ] docker-compose up starts all services
- [ ] Health checks for all services
- [ ] Data persists across restarts
- [ ] Environment variables properly configured

**Sub-tasks:**
- [ ] 33.1 Finalize backend Dockerfile with all dependencies
- [ ] 33.2 Finalize frontend Dockerfile with production build
- [ ] 33.3 Add Tesseract to backend Docker image
- [ ] 33.4 Configure service dependencies (depends_on with condition)
- [ ] 33.5 Add health checks for PostgreSQL, ChromaDB, backend, frontend
- [ ] 33.6 Configure volumes for data persistence
- [ ] 33.7 Add nginx or traefik for frontend/API routing (optional)
- [ ] 33.8 Create docker-compose.override.yml for development
- [ ] 33.9 Test full stack startup from scratch
- [ ] 33.10 Document resource requirements (RAM, disk)
- [ ] 33.11 Write startup/shutdown scripts

**Technical Notes:**
- Minimum resources: 8GB RAM, 10GB disk
- Use named volumes for PostgreSQL and ChromaDB data
- Backend: port 8000, Frontend: port 3000

---

### Task 34: Create sample contracts and seed data

**Type:** Testing
**Priority:** P1-High
**Dependencies:** Task 33
**PRD Reference:** OQ-1, D-8

**Description:**
Create sample contract documents and seed data for demos, covering all supported contract types and risk scenarios.

**Acceptance Criteria:**
- [ ] Sample contracts for all 6 types
- [ ] Contracts include various risk levels
- [ ] Seed users for all roles
- [ ] Data loading script works reliably

**Sub-tasks:**
- [ ] 34.1 Create sample NDA (low risk, standard terms)
- [ ] 34.2 Create sample NDA (high risk, unlimited liability)
- [ ] 34.3 Create sample MSA with SLAs and auto-renewal
- [ ] 34.4 Create sample SOW with obligations and deadlines
- [ ] 34.5 Create sample Vendor Agreement with spend commitment
- [ ] 34.6 Create sample Amendment to existing contract
- [ ] 34.7 Create sample Employment Contract
- [ ] 34.8 Create seed script for demo users (admin, legal, procurement)
- [ ] 34.9 Create seed script to upload and process sample contracts
- [ ] 34.10 Create reset script to clear and re-seed data
- [ ] 34.11 Document seed data for demo narrative

**Technical Notes:**
- Use realistic but fictional company names
- Include contracts expiring soon for demo urgency
- Include obligations due in next 30 days

---

### Task 35: Write demo script and user documentation

**Type:** Documentation
**Priority:** P1-High
**Dependencies:** Task 34
**PRD Reference:** D-8, D-9

**Description:**
Create demo script for sales presentations and user documentation for the MVP features.

**Acceptance Criteria:**
- [ ] Demo script with step-by-step instructions
- [ ] User guide covering all features
- [ ] README updated with full documentation
- [ ] Troubleshooting guide for common issues

**Sub-tasks:**
- [ ] 35.1 Write demo script introduction and setup
- [ ] 35.2 Write demo script: contract upload flow
- [ ] 35.3 Write demo script: exploring Legal dashboard
- [ ] 35.4 Write demo script: exploring Procurement dashboard
- [ ] 35.5 Write demo script: Q&A with sample questions
- [ ] 35.6 Write demo script: risk detection showcase
- [ ] 35.7 Write user guide: getting started
- [ ] 35.8 Write user guide: feature documentation
- [ ] 35.9 Update README with installation and usage
- [ ] 35.10 Write troubleshooting guide
- [ ] 35.11 Create FAQ document

**Technical Notes:**
- Demo should complete in 20-30 minutes
- Include sample questions for Q&A demo
- Screenshots for key flows

---

## Phase 8: Post-Signing Contract Management

*Competitive features based on Sirion Labs and Legitt AI research*

---

### Task 36: Implement obligation compliance workflow endpoints

**Type:** Backend
**Priority:** P1-High
**Dependencies:** Task 15, Task 22
**PRD Reference:** FR-8.1, FR-8.2, FR-8.3, FR-8.4, FR-8.5, FR-8.6

**Description:**
Build API endpoints for managing obligation compliance lifecycle: status updates, RAG status, owner assignment, recurring generation, and compliance evidence.

**Acceptance Criteria:**
- [ ] PUT /api/obligations/{id}/status updates obligation status
- [ ] PUT /api/obligations/{id}/rag updates RAG status with notes
- [ ] PUT /api/obligations/{id}/owner assigns owner
- [ ] POST /api/obligations/{id}/evidence uploads compliance evidence
- [ ] GET /api/compliance/rates returns compliance metrics

**Sub-tasks:**
- [ ] 36.1 Create ObligationUpdate Pydantic schemas
- [ ] 36.2 Implement PUT /api/obligations/{id}/status endpoint
- [ ] 36.3 Implement PUT /api/obligations/{id}/rag endpoint with notes
- [ ] 36.4 Implement PUT /api/obligations/{id}/owner endpoint
- [ ] 36.5 Create obligation evidence model (file attachment)
- [ ] 36.6 Implement POST /api/obligations/{id}/evidence endpoint
- [ ] 36.7 Implement recurring obligation auto-generation service
- [ ] 36.8 Create background job to generate recurring obligations
- [ ] 36.9 Implement GET /api/compliance/rates endpoint (by contract, owner, category)
- [ ] 36.10 Add audit logging for all obligation updates

**Technical Notes:**
- Status transitions: pending → in_progress → completed OR pending → overdue
- RAG status: green (on track), amber (at risk), red (overdue/failed)
- Evidence storage: local filesystem with metadata in DB

---

### Task 37: Implement SLA tracking and breach detection

**Type:** Backend
**Priority:** P1-High
**Dependencies:** Task 14, Task 15
**PRD Reference:** FR-8.7, FR-8.8, FR-8.9, FR-8.10, FR-8.11

**Description:**
Build SLA extraction from contracts and tracking system with breach detection and proactive alerts.

**Acceptance Criteria:**
- [ ] SLAs extracted and stored from contract clauses
- [ ] SLA performance can be logged against targets
- [ ] Breaches auto-detected and flagged
- [ ] Compliance percentages calculated per vendor

**Sub-tasks:**
- [ ] 37.1 Create ContractSLA model (target, metric_type, threshold, penalty)
- [ ] 37.2 Create SLAPerformance model (actual_value, recorded_at)
- [ ] 37.3 Create Alembic migration for SLA tables
- [ ] 37.4 Extend Clause Extraction Agent to identify SLA clauses
- [ ] 37.5 Create SLA extraction service to parse SLA terms
- [ ] 37.6 Implement POST /api/sla/{contract_id}/performance endpoint
- [ ] 37.7 Implement breach detection logic (compare actual vs target)
- [ ] 37.8 Create SLA breach alert generation
- [ ] 37.9 Implement GET /api/sla/compliance endpoint (per vendor/contract)
- [ ] 37.10 Add SLA summary to procurement dashboard

**Technical Notes:**
- SLA types: response_time, uptime_percentage, resolution_time, delivery_time
- Breach severity: minor (<5% miss), moderate (5-15% miss), critical (>15% miss)
- Store SLA performance history for trend analysis

---

### Task 38: Implement renewal management system

**Type:** Backend
**Priority:** P1-High
**Dependencies:** Task 17
**PRD Reference:** FR-8.12, FR-8.13, FR-8.14, FR-8.15, FR-8.16

**Description:**
Build comprehensive renewal management with calendar view, notice period tracking, and renewal recommendations.

**Acceptance Criteria:**
- [ ] Renewal calendar shows 90/60/30 day windows
- [ ] Auto-renewal contracts flagged with countdowns
- [ ] Notice period deadline alerts generated
- [ ] Renewal recommendations based on performance

**Sub-tasks:**
- [ ] 38.1 Create renewal calendar endpoint GET /api/renewals/calendar
- [ ] 38.2 Return contracts grouped by renewal window (90/60/30 days)
- [ ] 38.3 Calculate notice period deadlines from expiration
- [ ] 38.4 Create renewal alert generation service
- [ ] 38.5 Implement GET /api/renewals/at-risk endpoint (past notice deadline)
- [ ] 38.6 Create renewal recommendation engine (based on vendor performance, spend)
- [ ] 38.7 Implement GET /api/renewals/{contract_id}/recommendation endpoint
- [ ] 38.8 Add renewal status tracking (pending_review, approved, declined, auto_renewed)
- [ ] 38.9 Implement PUT /api/contracts/{id}/renewal-decision endpoint
- [ ] 38.10 Add renewal dashboard widget data endpoint

**Technical Notes:**
- Alert windows: 90 days (initial), 60 days (reminder), 30 days (urgent), 7 days (critical)
- Recommendation factors: vendor compliance rate, spend value, SLA performance

---

### Task 39: Implement amendment and version tracking

**Type:** Backend
**Priority:** P2-Medium
**Dependencies:** Task 19
**PRD Reference:** FR-8.17, FR-8.18, FR-8.19, FR-8.20, FR-8.21

**Description:**
Build contract version tracking for amendments with change history and audit trail.

**Acceptance Criteria:**
- [ ] Amendments linked to parent contracts
- [ ] Version history maintained with numbering
- [ ] Change summary generated between versions
- [ ] Full audit trail of modifications

**Sub-tasks:**
- [ ] 39.1 Extend contract_links table with version_number field
- [ ] 39.2 Create amendment upload flow that auto-links to parent
- [ ] 39.3 Implement GET /api/contracts/{id}/versions endpoint
- [ ] 39.4 Create contract diff service (compare key terms between versions)
- [ ] 39.5 Implement GET /api/contracts/{id}/diff/{version_id} endpoint
- [ ] 39.6 Implement supersedes relationship handling
- [ ] 39.7 Mark superseded contracts as inactive
- [ ] 39.8 Create amendment summary extraction (what changed)
- [ ] 39.9 Add version history to contract viewer
- [ ] 39.10 Add audit trail endpoint GET /api/contracts/{id}/audit-trail

**Technical Notes:**
- Diff comparison: compare extracted metadata fields
- Supersedes: when new contract fully replaces old, mark old as superseded
- Preserve all versions, never delete

---

### Task 40: Implement vendor performance scoring

**Type:** Backend
**Priority:** P1-High
**Dependencies:** Task 36, Task 37
**PRD Reference:** FR-8.22, FR-8.23, FR-8.24, FR-8.25, FR-8.26

**Description:**
Build vendor performance scoring system aggregating compliance, SLA, and spend data per counterparty.

**Acceptance Criteria:**
- [ ] Vendor performance score calculated (0-100)
- [ ] SLA compliance rates tracked per vendor
- [ ] Spend and exposure aggregated per vendor
- [ ] At-risk vendors identified automatically

**Sub-tasks:**
- [ ] 40.1 Create VendorPerformance model (aggregate metrics per counterparty)
- [ ] 40.2 Create vendor performance calculation service
- [ ] 40.3 Calculate obligation compliance rate per vendor
- [ ] 40.4 Calculate SLA compliance rate per vendor
- [ ] 40.5 Aggregate spend exposure per vendor
- [ ] 40.6 Calculate composite performance score (weighted factors)
- [ ] 40.7 Implement GET /api/vendors endpoint (list with scores)
- [ ] 40.8 Implement GET /api/vendors/{name}/performance endpoint
- [ ] 40.9 Identify at-risk vendors (score < threshold)
- [ ] 40.10 Create vendor comparison endpoint GET /api/vendors/compare
- [ ] 40.11 Add vendor scorecard to procurement dashboard

**Technical Notes:**
- Score factors: obligation compliance (40%), SLA compliance (30%), responsiveness (20%), issue rate (10%)
- At-risk threshold: score < 60
- Normalize counterparty names for accurate aggregation

---

### Task 41: Implement milestone health dashboard

**Type:** Backend + Frontend
**Priority:** P1-High
**Dependencies:** Task 36, Task 40
**PRD Reference:** FR-8.27, FR-8.28, FR-8.29, FR-8.30

**Description:**
Build milestone health dashboard showing status of all milestones across the portfolio with at-risk detection.

**Acceptance Criteria:**
- [ ] Milestone status overview (upcoming, at-risk, missed, completed)
- [ ] At-risk contracts auto-detected
- [ ] Portfolio-level compliance metrics displayed
- [ ] Milestone owner assignment supported

**Sub-tasks:**
- [ ] 41.1 Create milestone aggregation query (all obligations as milestones)
- [ ] 41.2 Implement GET /api/milestones/health endpoint
- [ ] 41.3 Return milestones by status with counts
- [ ] 41.4 Implement at-risk detection logic (approaching deadline + no progress)
- [ ] 41.5 Implement GET /api/contracts/at-risk endpoint
- [ ] 41.6 Create portfolio compliance metrics endpoint
- [ ] 41.7 Implement milestone owner assignment
- [ ] 41.8 Create MilestoneHealthWidget frontend component
- [ ] 41.9 Create AtRiskContractsWidget frontend component
- [ ] 41.10 Add milestone health to portfolio dashboard

**Technical Notes:**
- At-risk: deadline within 7 days AND status = pending
- Compliance rate: completed / (completed + overdue) × 100
- Group milestones by: this week, next week, this month, future

---

### Task 42: Implement compliance reporting

**Type:** Backend
**Priority:** P2-Medium
**Dependencies:** Task 36, Task 40, Task 41
**PRD Reference:** FR-8.31, FR-8.32, FR-8.33, FR-8.34

**Description:**
Build compliance reporting system with export capabilities and trend analysis.

**Acceptance Criteria:**
- [ ] Compliance reports generated by time period
- [ ] Export to CSV/Excel for audit purposes
- [ ] Trend analysis shows compliance over time
- [ ] Scheduled report generation supported

**Sub-tasks:**
- [ ] 42.1 Create compliance report data aggregation service
- [ ] 42.2 Implement GET /api/reports/compliance endpoint with date range
- [ ] 42.3 Create CSV export service
- [ ] 42.4 Implement GET /api/reports/compliance/export endpoint
- [ ] 42.5 Create compliance trend calculation (weekly/monthly)
- [ ] 42.6 Implement GET /api/reports/compliance/trend endpoint
- [ ] 42.7 Create scheduled report configuration model
- [ ] 42.8 Implement report scheduling background job
- [ ] 42.9 Add report download UI component
- [ ] 42.10 Add compliance trend chart to dashboard

**Technical Notes:**
- Export formats: CSV, Excel (using openpyxl)
- Trend periods: last 4 weeks, last 3 months, last 12 months
- Schedule options: daily, weekly, monthly

---

### Task 43: Implement post-signing dashboard views

**Type:** Frontend
**Priority:** P1-High
**Dependencies:** Task 36-42
**PRD Reference:** FR-8.x

**Description:**
Build frontend dashboard components for post-signing contract management features.

**Acceptance Criteria:**
- [ ] Compliance management page with obligation list
- [ ] SLA tracking dashboard with breach alerts
- [ ] Renewal calendar with notifications
- [ ] Vendor performance scorecard

**Sub-tasks:**
- [ ] 43.1 Create ComplianceManagementPage component
- [ ] 43.2 Create ObligationList with status update actions
- [ ] 43.3 Create RAGStatusBadge component
- [ ] 43.4 Create SLADashboardPage component
- [ ] 43.5 Create SLAPerformanceChart component
- [ ] 43.6 Create BreachAlertsList component
- [ ] 43.7 Create RenewalCalendarPage component
- [ ] 43.8 Create RenewalCalendarWidget (month view)
- [ ] 43.9 Create VendorScorecardPage component
- [ ] 43.10 Create VendorComparisonTable component
- [ ] 43.11 Create MilestoneHealthPage component
- [ ] 43.12 Add navigation items for new pages

**Technical Notes:**
- Calendar: use react-big-calendar or similar
- Charts: use Recharts for performance trends
- Color coding: green (compliant), amber (at-risk), red (breach/overdue)

---

## Implementation Notes

### Cross-Cutting Concerns

1. **Error Handling**: Implement consistent error responses across all endpoints (use FastAPI exception handlers)
2. **Logging**: Use structured logging with correlation IDs for request tracing
3. **Configuration**: All secrets via environment variables, never hardcoded
4. **CORS**: Configure CORS for frontend-backend communication in development
5. **API Versioning**: Prefix all endpoints with /api/v1 (optional for MVP)

### Known Risks

1. **LLM Costs**: GPT-4o calls can be expensive; monitor via Langfuse dashboard
2. **OCR Quality**: Scanned PDFs may have poor OCR results; flag for manual review
3. **Chunking Accuracy**: Legal documents vary widely; may need tuning per contract type
4. **Demo Data Quality**: Sample contracts must be realistic for credible demos

### Deferred Features (Future Phases)

1. Email alerts via Outlook/SMTP (FR-6.x)
2. Deviation Detection skill (SK-007) - requires playbook setup
3. Advanced playbook management UI
4. Contract comparison side-by-side view
5. ~~Export reports to PDF/Excel~~ **Now in Phase 8 (Task 42)**
6. Calendar integration (Google, Outlook) for milestone reminders
7. Slack/Teams notifications for obligation alerts
8. AI-powered renewal negotiation recommendations

---

## Phase 9: Relationship Governance (Evaluetor Features)

*Business relationship management with KPI perception scoring and improvement tracking*

---

### Task 44: Create business relationship data model

**Type:** Backend
**Priority:** P2-Medium
**Dependencies:** Task 2
**PRD Reference:** Evaluetor Requirements

**Description:**
Create data model for business relationships between organizations, governance structures, and team assignments.

**Acceptance Criteria:**
- [x] Organization model with type, industry, size, region
- [x] BusinessRelationship model linking organizations
- [x] RelationshipTeam model for team assignments
- [x] GovernanceModel for tiers and escalation rules
- [x] Migrations run successfully

**Sub-tasks:**
- [x] 44.1 Create Organization model (id, name, type, industry, size, region, relationship_owner)
- [x] 44.2 Create BusinessRelationship model (id, org_a_id, org_b_id, type, status, health_score, governance_model_id)
- [x] 44.3 Create RelationshipTeam model (id, user_id, relationship_id, role, responsibilities)
- [x] 44.4 Create GovernanceModel model (id, name, tiers, escalation_rules, review_frequency)
- [x] 44.5 Add relationship_id foreign key to Contract model
- [x] 44.6 Create Alembic migration for all new tables
- [x] 44.7 Create Pydantic schemas for all new models

**Technical Notes:**
- Organization types: customer, vendor, partner, internal
- Relationship types: customer, supplier, partner, joint_venture
- Health score: 0-100 composite score

---

### Task 45: Implement organization and relationship APIs

**Type:** Backend
**Priority:** P2-Medium
**Dependencies:** Task 44
**PRD Reference:** Evaluetor Requirements

**Description:**
Build REST API endpoints for organization and relationship management.

**Acceptance Criteria:**
- [x] CRUD endpoints for organizations
- [x] CRUD endpoints for relationships
- [x] Team assignment endpoints
- [x] Health score calculation

**Sub-tasks:**
- [x] 45.1 Create organizations router (app/routers/organizations.py)
- [x] 45.2 Implement POST /api/organizations endpoint
- [x] 45.3 Implement GET /api/organizations (list with filters)
- [x] 45.4 Implement GET /api/organizations/{id} with linked relationships
- [x] 45.5 Implement PUT /api/organizations/{id}
- [x] 45.6 Create relationships router (app/routers/relationships.py)
- [x] 45.7 Implement POST /api/relationships endpoint
- [x] 45.8 Implement GET /api/relationships (list with filters)
- [x] 45.9 Implement GET /api/relationships/{id} with teams and contracts
- [x] 45.10 Implement POST /api/relationships/{id}/teams (assign team members)
- [x] 45.11 Create relationship health score calculation service
- [ ] 45.12 Add organization auto-creation from contract metadata extraction

**Technical Notes:**
- Normalize organization names to avoid duplicates
- Health score factors: compliance rate, SLA performance, issue count, satisfaction

---

### Task 46: Implement KPI definition and management

**Type:** Backend
**Priority:** P2-Medium
**Dependencies:** Task 45
**PRD Reference:** Evaluetor Requirements

**Description:**
Build KPI definition system for tracking performance metrics per relationship.

**Acceptance Criteria:**
- [x] KPI model with targets and thresholds
- [x] CRUD endpoints for KPIs
- [ ] KPI template library
- [x] KPIs linked to relationships

**Sub-tasks:**
- [x] 46.1 Create KPI model (id, relationship_id, name, description, measurement_type, target, threshold_amber, threshold_red)
- [x] 46.2 Create KPICategory model (id, name, description)
- [x] 46.3 Create Alembic migration for KPI tables
- [x] 46.4 Create kpis router (app/routers/kpis.py)
- [x] 46.5 Implement POST /api/relationships/{id}/kpis endpoint
- [x] 46.6 Implement GET /api/relationships/{id}/kpis (list KPIs)
- [x] 46.7 Implement PUT /api/kpis/{id} (update KPI definition)
- [x] 46.8 Implement DELETE /api/kpis/{id}
- [ ] 46.9 Create KPI template library (common KPIs for contract types)
- [ ] 46.10 Implement POST /api/relationships/{id}/kpis/from-template

**Technical Notes:**
- Measurement types: percentage, number, currency, time, boolean
- Common KPIs: response_time, uptime, delivery_on_time, quality_score, satisfaction

---

### Task 47: Implement perception scoring system

**Type:** Backend
**Priority:** P2-Medium
**Dependencies:** Task 46
**PRD Reference:** Evaluetor Requirements

**Description:**
Build the perception scoring system that captures internal and external KPI perception scores with gap analysis.

**Acceptance Criteria:**
- [x] Internal scores captured per KPI
- [x] External scores captured per KPI
- [x] Gap calculation between internal/external
- [x] Gap severity classification
- [ ] Trend analysis over time

**Sub-tasks:**
- [x] 47.1 Create PerceptionScore model (id, kpi_id, scorer_org_id, score, period, comments, scored_by, scored_at)
- [x] 47.2 Create PerceptionGap model (id, kpi_id, period, internal_score, external_score, gap, gap_severity)
- [x] 47.3 Create Alembic migration for perception tables
- [x] 47.4 Create perception router (app/routers/kpis.py with perception endpoints)
- [x] 47.5 Implement POST /api/kpis/{id}/scores endpoint (submit score)
- [x] 47.6 Implement GET /api/kpis/{id}/scores (list scores by period)
- [x] 47.7 Create gap calculation service (compare internal vs external)
- [x] 47.8 Implement GET /api/relationships/{id}/perception-gaps
- [x] 47.9 Create gap severity classification (minor, moderate, significant, critical)
- [ ] 47.10 Implement trend analysis for scores over time
- [x] 47.11 Create external scoring portal API (token-based access)

**Technical Notes:**
- Score range: 1-10
- Gap severity: minor (<1 point), moderate (1-2), significant (2-3), critical (>3)
- Period: quarterly or monthly

---

### Task 48: Implement improvement point tracking

**Type:** Backend
**Priority:** P2-Medium
**Dependencies:** Task 47
**PRD Reference:** Evaluetor Requirements

**Description:**
Build improvement point management linked to KPI gaps.

**Acceptance Criteria:**
- [x] Improvement points linked to gaps
- [x] Status workflow (open → in_progress → completed)
- [x] Action items per improvement
- [x] Auto-generation from critical gaps

**Sub-tasks:**
- [x] 48.1 Create ImprovementPoint model (id, relationship_id, kpi_id, gap_id, title, description, priority, status, owner, due_date)
- [x] 48.2 Create ImprovementAction model (id, improvement_id, description, status, owner, due_date, completed_at)
- [x] 48.3 Create Alembic migration
- [x] 48.4 Create improvements router (app/routers/improvements.py)
- [x] 48.5 Implement POST /api/relationships/{id}/improvements endpoint
- [x] 48.6 Implement GET /api/relationships/{id}/improvements (list with filters)
- [x] 48.7 Implement PUT /api/improvements/{id} (status update)
- [x] 48.8 Implement POST /api/improvements/{id}/actions (add action item)
- [x] 48.9 Create auto-improvement generation from critical gaps
- [x] 48.10 Implement improvement completion workflow
- [ ] 48.11 Add improvement metrics to relationship health score

**Technical Notes:**
- Priority: low, medium, high, critical
- Status: open, in_progress, completed, cancelled
- Auto-generate improvement for gaps with severity >= significant

---

### Task 49: Implement Business Leader dashboard

**Type:** Backend + Frontend
**Priority:** P2-Medium
**Dependencies:** Task 47, Task 48
**PRD Reference:** Evaluetor Requirements

**Description:**
Build the Business Leader dashboard with perception charts, satisfaction trends, and improvement tracking (Evaluetor-style).

**Acceptance Criteria:**
- [ ] Perception gap summary across relationships
- [ ] Satisfaction trend charts
- [ ] Improvement status summary
- [ ] Relationship health scorecard

**Sub-tasks:**
- [ ] 49.1 Create BusinessLeaderDashboardResponse Pydantic schema
- [ ] 49.2 Implement GET /api/dashboard/business-leader endpoint
- [ ] 49.3 Return perception gap summary across relationships
- [ ] 49.4 Return satisfaction trend data (quarterly/annual)
- [ ] 49.5 Return improvement point status summary
- [ ] 49.6 Create BusinessLeaderDashboardPage component
- [ ] 49.7 Create PerceptionGapChart component (bar chart: internal vs external)
- [ ] 49.8 Create SatisfactionTrendChart component (line chart over time)
- [ ] 49.9 Create ImprovementStatusWidget component
- [ ] 49.10 Create RelationshipHealthScorecard component

**Technical Notes:**
- Use Recharts for visualizations
- Perception gap chart: side-by-side bars per KPI
- Trend chart: 4 quarters or 12 months

---

### Task 50: Implement Account Manager dashboard

**Type:** Backend + Frontend
**Priority:** P2-Medium
**Dependencies:** Task 45, Task 48
**PRD Reference:** Evaluetor Requirements

**Description:**
Build the Account Manager dashboard for managing specific business relationships (Evaluetor-style).

**Acceptance Criteria:**
- [ ] Assigned relationships with health scores
- [ ] Commitments and deadlines
- [ ] KPI alerts
- [ ] Relationship detail view

**Sub-tasks:**
- [ ] 50.1 Create AccountManagerDashboardResponse Pydantic schema
- [ ] 50.2 Implement GET /api/dashboard/account-manager endpoint
- [ ] 50.3 Return assigned relationships with health scores
- [ ] 50.4 Return commitments and deadlines for relationships
- [ ] 50.5 Return alerts (upcoming reviews, at-risk KPIs)
- [ ] 50.6 Create AccountManagerDashboardPage component
- [ ] 50.7 Create RelationshipsList component with health indicators
- [ ] 50.8 Create CommitmentsTimeline component
- [ ] 50.9 Create KPIAlerts component
- [ ] 50.10 Create RelationshipDetailView component

**Technical Notes:**
- Filter relationships by current user as relationship_owner
- Health indicators: green (>80), amber (60-80), red (<60)

---

### Task 51: Implement governance structure management

**Type:** Backend + Frontend
**Priority:** P3-Low
**Dependencies:** Task 45
**PRD Reference:** Evaluetor Requirements

**Description:**
Build governance structure visualization and management.

**Acceptance Criteria:**
- [ ] Governance tier definitions
- [ ] Team hierarchy visualization
- [ ] Review scheduling
- [ ] Escalation configuration

**Sub-tasks:**
- [ ] 51.1 Create governance tier definitions (operational, tactical, strategic)
- [ ] 51.2 Implement GET /api/relationships/{id}/governance endpoint
- [ ] 51.3 Implement PUT /api/relationships/{id}/governance (update structure)
- [ ] 51.4 Create governance review scheduling
- [ ] 51.5 Create GovernanceStructurePage component
- [ ] 51.6 Create OrgChartVisualization component (team hierarchy)
- [ ] 51.7 Create GovernanceReviewCalendar component
- [ ] 51.8 Add escalation workflow configuration

**Technical Notes:**
- Governance tiers: operational (weekly), tactical (monthly), strategic (quarterly)
- Use react-organizational-chart or similar for visualization

---

## Phase 10: Mobile & Surveys (Evaluetor Features)

*External stakeholder engagement and mobile access*

---

### Task 52: Implement satisfaction survey system

**Type:** Backend
**Priority:** P3-Low
**Dependencies:** Task 47
**PRD Reference:** Evaluetor Requirements

**Description:**
Build survey system for collecting multi-party satisfaction scores.

**Acceptance Criteria:**
- [x] Survey template builder
- [ ] Survey distribution via email
- [x] Public response collection
- [ ] Response aggregation

**Sub-tasks:**
- [x] 52.1 Create SurveyTemplate model (id, name, questions, frequency, is_active)
- [x] 52.2 Create SurveyQuestion model (id, template_id, text, type, options, required)
- [x] 52.3 Create SurveyInstance model (id, template_id, relationship_id, period, status, sent_at, due_date)
- [x] 52.4 Create SurveyResponse model (id, survey_id, respondent_email, respondent_org_id, answers, submitted_at)
- [x] 52.5 Create Alembic migration
- [x] 52.6 Create surveys router (app/routers/surveys.py)
- [x] 52.7 Implement POST /api/surveys/templates endpoint
- [x] 52.8 Implement POST /api/relationships/{id}/surveys (create instance)
- [ ] 52.9 Create survey distribution service (email links)
- [x] 52.10 Create public survey submission endpoint (token-based)
- [ ] 52.11 Implement survey response aggregation
- [ ] 52.12 Create SurveyBuilderPage component
- [ ] 52.13 Create SurveyResponsePortal component (external-facing)
- [ ] 52.14 Create SurveyResultsPage component

**Technical Notes:**
- Question types: rating (1-10), multiple_choice, text, yes_no
- Survey status: draft, sent, completed, expired
- Token-based access for external respondents

---

### Task 53: Implement external stakeholder portal

**Type:** Backend + Frontend
**Priority:** P3-Low
**Dependencies:** Task 47, Task 52
**PRD Reference:** Evaluetor Requirements

**Description:**
Build minimal external portal for clients/vendors to submit perception scores and survey responses.

**Acceptance Criteria:**
- [x] Token-based access (no registration)
- [ ] Perception scoring form
- [x] Survey submission form
- [ ] Branded portal UI

**Sub-tasks:**
- [x] 53.1 Create ExternalAccessToken model (id, token, type, relationship_id, org_id, expires_at, used_at)
- [x] 53.2 Create external access token generation service
- [x] 53.3 Implement GET /api/external/{token}/context (relationship + KPIs)
- [ ] 53.4 Implement POST /api/external/{token}/scores (submit perception)
- [x] 53.5 Implement POST /api/external/{token}/survey (submit survey)
- [ ] 53.6 Create ExternalPortalLayout component (minimal, branded)
- [ ] 53.7 Create PerceptionScoringForm component
- [ ] 53.8 Create SurveyForm component
- [ ] 53.9 Create ThankYouPage component
- [ ] 53.10 Add portal branding configuration

**Technical Notes:**
- Tokens expire after 30 days
- Rate limit: 10 submissions per token
- Minimal UI, mobile-friendly

---

### Task 54: Implement Progressive Web App (Mobile)

**Type:** Frontend
**Priority:** P3-Low
**Dependencies:** Task 43
**PRD Reference:** Evaluetor Requirements

**Description:**
Convert React app to PWA for mobile access.

**Acceptance Criteria:**
- [ ] Installable on mobile devices
- [ ] Offline caching for key pages
- [ ] Push notifications
- [ ] Mobile-optimized UI

**Sub-tasks:**
- [ ] 54.1 Add PWA manifest.json with app metadata
- [ ] 54.2 Configure service worker for offline caching
- [ ] 54.3 Add install prompt for mobile browsers
- [ ] 54.4 Optimize UI for mobile viewports (responsive)
- [ ] 54.5 Create mobile-optimized navigation (bottom tabs)
- [ ] 54.6 Add push notification support
- [ ] 54.7 Create mobile dashboard views (simplified widgets)
- [ ] 54.8 Test on iOS Safari and Android Chrome
- [ ] 54.9 Add app icons for home screen (multiple sizes)
- [ ] 54.10 Document PWA installation steps

**Technical Notes:**
- Use Workbox for service worker management
- Cache strategy: network-first for API, cache-first for assets
- Icons: 192x192 and 512x512 PNG

---

## Implementation Notes

### Phase 9-10 Cross-Cutting Concerns

1. **External Portal Security**: Token-based access with expiration, rate limiting, no PII exposure
2. **Multi-tenancy**: Organizations must be isolated; relationships only visible to participants
3. **Data Migration**: Provide import scripts for existing organization/relationship data
4. **Localization**: Survey forms should support multiple languages (future)
5. **GDPR Compliance**: Perception scores and survey responses are personal data; implement consent and deletion

### Phase 9-10 Known Risks

1. **External Engagement**: Clients/vendors may not respond to perception surveys
2. **Data Quality**: Self-reported scores may be biased; consider validation
3. **Complexity**: Relationship governance adds significant UI complexity
4. **Scope Creep**: Clear boundaries between contract intelligence and relationship governance

---

*Last Updated: 2026-02-14*
*Changes:*
- *2025-02-01: Migrated from DSPy to Agent Squad + OpenAI + Langfuse*
- *2026-02-01: Added Phase 8 - Post-Signing Contract Management (Tasks 36-43) based on Sirion Labs and Legitt AI competitive analysis*
- *2026-02-14: Added Phase 9 - Relationship Governance (Tasks 44-51) and Phase 10 - Mobile & Surveys (Tasks 52-54) based on Evaluetor competitive analysis*
- *2026-02-14: Implemented Phase 9 backend (Tasks 44-48: models, routers, schemas for Organizations, Relationships, KPIs, Perception Scoring, Improvements)*
- *2026-02-14: Implemented Phase 10 backend surveys (Task 52-53: Survey models, templates, instances, external token-based access). Task 54 (PWA) deferred per requirement.*
- *2026-02-14: Created seed script for relationship governance data (scripts/seed_relationship_governance.py)*
