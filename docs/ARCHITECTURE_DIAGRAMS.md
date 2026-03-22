# CLM Architecture & Sequence Diagrams

> Comprehensive visual documentation of the Contract Lifecycle Management system architecture and data flows.

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Detailed Component Architecture](#2-detailed-component-architecture)
3. [Database Schema Diagram](#3-database-schema-diagram)
4. [Sequence Diagrams](#4-sequence-diagrams)
   - [Contract Upload & Processing](#41-contract-upload--processing-flow)
   - [Contract Q&A (RAG)](#42-contract-qa-rag-flow)
   - [SLA Comparison & Alerts](#43-sla-comparison--alert-flow)
   - [Scheduled Job Execution](#44-scheduled-job-execution-flow)
   - [User Authentication](#45-user-authentication-flow)
   - [Workflow Execution](#46-workflow-execution-flow)
5. [Data Flow Diagrams](#5-data-flow-diagrams)

---

## 1. System Architecture Overview

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        Browser["React Frontend<br/>TypeScript + TailwindCSS"]
        Mobile["Mobile/API Clients"]
    end

    subgraph Gateway["API Gateway"]
        FastAPI["FastAPI Server<br/>Async Python 3.11+"]
        Auth["JWT Authentication<br/>RBAC Middleware"]
        CORS["CORS Middleware"]
    end

    subgraph Core["Core Services"]
        direction TB
        Orchestrator["Agent Orchestrator<br/>Intent Classification"]
        Indexer["Indexing Pipeline<br/>Parse → Chunk → Store"]
        Scheduler["Scheduler Service<br/>Background Jobs"]
        Notification["Notification Service<br/>Email/Slack/Webhook"]
        RelGov["Relationship Governance<br/>KPI/Perception/Improvements"]
    end

    subgraph AI["AI/ML Layer"]
        direction TB
        Agents["8 Specialized Agents"]
        LLM["OpenAI GPT-4o"]
        Langfuse["Langfuse<br/>Observability"]
    end

    subgraph Data["Data Layer"]
        direction TB
        PostgreSQL[("PostgreSQL<br/>Structured Data")]
        ChromaDB[("ChromaDB<br/>Vector Store")]
        FileStore[("File Storage<br/>Contracts/Docs")]
    end

    subgraph External["External Integrations"]
        ServiceNow["ServiceNow<br/>ITSM Data"]
        Salesforce["Salesforce<br/>CRM Data"]
        Email["SMTP Server<br/>Email Delivery"]
    end

    Browser --> FastAPI
    Mobile --> FastAPI
    FastAPI --> Auth
    Auth --> CORS

    CORS --> Orchestrator
    CORS --> Indexer
    CORS --> Scheduler
    CORS --> Notification

    Orchestrator --> Agents
    Agents --> LLM
    Agents --> Langfuse
    LLM --> Langfuse

    Orchestrator --> ChromaDB
    Indexer --> ChromaDB
    Indexer --> PostgreSQL
    Indexer --> FileStore

    Scheduler --> PostgreSQL
    Notification --> Email

    Core --> External

    style Browser fill:#61DAFB
    style FastAPI fill:#009688
    style PostgreSQL fill:#336791
    style ChromaDB fill:#FF6B6B
    style LLM fill:#10A37F
    style Langfuse fill:#7C3AED
```

---

## 2. Detailed Component Architecture

```mermaid
flowchart TB
    subgraph Frontend["Frontend (React + TypeScript)"]
        direction LR
        Pages["Pages<br/>Dashboard, Contracts,<br/>Query, Admin"]
        Components["Components<br/>Tables, Forms,<br/>Charts, Cards"]
        Hooks["Hooks<br/>useAuth, useQuery,<br/>useMutation"]
        API_Client["API Client<br/>Axios/Fetch"]
    end

    subgraph Routers["API Routers (29 routers)"]
        direction TB
        subgraph Business["Business APIs"]
            R_Contracts["contracts.py<br/>/api/contracts"]
            R_Query["query.py<br/>/api/query"]
            R_Obligations["obligations.py<br/>/api/obligations"]
            R_SLA["sla.py<br/>/api/sla"]
            R_Renewals["renewals.py<br/>/api/renewals"]
        end
        subgraph Admin["Admin APIs"]
            R_Scheduler["scheduler_admin.py<br/>/api/admin/scheduler"]
            R_MasterData["master_data_admin.py<br/>/api/admin/master-data"]
            R_Users["users.py<br/>/api/users"]
            R_Audit["audit.py<br/>/api/audit"]
        end
        subgraph Analytics["Analytics APIs"]
            R_Dashboard["dashboard.py<br/>/api/dashboard"]
            R_Reports["reports.py<br/>/api/reports"]
            R_Monitor["monitor.py<br/>/api/monitor"]
        end
        subgraph Governance["Relationship Governance APIs"]
            R_Orgs["organizations.py<br/>/api/organizations"]
            R_Rels["relationships.py<br/>/api/relationships"]
            R_KPIs["kpis.py<br/>/api/kpis"]
            R_Surveys["surveys.py<br/>/api/surveys"]
        end
    end

    subgraph Services["Services Layer (23 services)"]
        direction TB
        subgraph Processing["Document Processing"]
            S_Upload["upload.py<br/>File Handling"]
            S_Parser["parser.py<br/>PDF/DOCX Parser"]
            S_Chunker["chunker.py<br/>Semantic Chunking"]
            S_Indexer["indexer.py<br/>Vector Indexing"]
        end
        subgraph Core_Svc["Core Services"]
            S_Orchestrator["orchestrator.py<br/>Agent Routing"]
            S_Contracts["contracts.py<br/>CRUD Operations"]
            S_Scheduler["scheduler_service.py<br/>Job Management"]
            S_Notification["notification_service.py<br/>Delivery"]
        end
        subgraph Analysis["Analysis Services"]
            S_SLA_Compare["sla_comparison.py<br/>Performance Analysis"]
            S_SLA_Alert["sla_alert_service.py<br/>Breach Detection"]
            S_Calculation["calculation_service.py<br/>Metrics"]
        end
    end

    subgraph Agents["AI Agents (8 agents)"]
        direction LR
        A_QA["Contract Q&A<br/>RAG + Citations"]
        A_Metadata["Metadata<br/>Extraction"]
        A_Clause["Clause<br/>Extraction"]
        A_Obligation["Obligation<br/>Tracking"]
        A_Risk["Risk<br/>Detection"]
        A_Renewal["Renewal<br/>Monitoring"]
        A_SLA["SLA<br/>Extraction"]
        A_Schema["Schema<br/>Extraction"]
    end

    subgraph Connectors["External Connectors"]
        direction LR
        C_ServiceNow["ServiceNow<br/>Stub"]
        C_Milestone["Milestone<br/>Stub"]
        C_FX["FX Rates<br/>Stub"]
    end

    subgraph Storage["Data Storage"]
        direction TB
        DB_Postgres[("PostgreSQL<br/>50+ Tables")]
        DB_Chroma[("ChromaDB<br/>Vector Embeddings")]
        DB_Files[("File System<br/>uploads/processed")]
    end

    subgraph External_AI["AI Infrastructure"]
        direction LR
        OpenAI["OpenAI API<br/>GPT-4o"]
        Langfuse_Svc["Langfuse<br/>Tracing & Prompts"]
    end

    Frontend --> Routers
    Routers --> Services
    Services --> Agents
    Services --> Connectors
    Services --> Storage
    Agents --> External_AI
    Agents --> DB_Chroma

    style Frontend fill:#61DAFB
    style Routers fill:#009688
    style Services fill:#FF9800
    style Agents fill:#9C27B0
    style Storage fill:#336791
    style External_AI fill:#10A37F
```

---

## 3. Database Schema Diagram

```mermaid
erDiagram
    contracts ||--o{ clauses : has
    contracts ||--o{ obligations : has
    contracts ||--o{ contract_slas : has
    contracts ||--o{ contract_financials : has
    contracts ||--o{ contract_liabilities : has
    contracts ||--o{ contract_parties : has
    contracts ||--o{ contract_key_dates : has
    contracts ||--|| contract_clause_indicators : has
    contracts ||--o{ contract_links : parent
    contracts ||--o{ contract_links : child
    contracts ||--o{ sla_comparison_results : has
    contracts ||--o{ sla_alerts : has
    contracts ||--o{ events : triggers
    contracts }o--|| business_relationships : belongs_to

    contract_slas ||--o{ sla_performances : tracks
    contract_slas ||--o{ sla_comparison_results : compared

    scheduler_jobs ||--o{ scheduler_job_history : logs

    users ||--o{ audit_logs : creates
    users ||--o{ approval_requests : requests
    users ||--o{ relationship_teams : member_of

    workflow_definitions ||--o{ workflow_steps : contains
    workflow_definitions ||--o{ action_executions : triggers

    organizations ||--o{ business_relationships : participates_in
    business_relationships ||--o{ relationship_teams : has
    business_relationships ||--o{ kpis : tracks
    business_relationships ||--o{ improvement_points : has
    business_relationships ||--o{ survey_instances : has

    kpis ||--o{ perception_scores : measures
    kpis ||--o{ perception_gaps : calculates
    kpis ||--o{ improvement_points : linked_to

    survey_templates ||--o{ survey_questions : contains
    survey_templates ||--o{ survey_instances : creates
    survey_instances ||--o{ survey_responses : collects

    contracts {
        uuid id PK
        string filename
        string file_path
        enum contract_type
        string counterparty
        date effective_date
        date expiration_date
        decimal contract_value
        string currency
        enum risk_level
        int risk_score
        boolean auto_renewal
        int notice_period_days
        jsonb schema_data
        enum status
        timestamp created_at
        timestamp updated_at
    }

    obligations {
        uuid id PK
        uuid contract_id FK
        text description
        enum obligation_type
        enum owner_type
        enum category
        enum frequency
        date deadline
        enum status
        enum rag_status
        boolean is_critical
        int priority
    }

    contract_slas {
        uuid id PK
        uuid contract_id FK
        string sla_name
        string metric_type
        decimal target_value
        decimal minimum_value
        string measurement_period
        string penalty_terms
    }

    sla_comparison_results {
        uuid id PK
        uuid contract_id FK
        uuid sla_id FK
        date comparison_date
        decimal contracted_value
        decimal actual_value
        decimal variance
        boolean is_breach
        enum breach_severity
        string source_system
    }

    sla_alerts {
        uuid id PK
        uuid contract_id FK
        uuid sla_id FK
        enum severity
        string title
        text message
        boolean is_acknowledged
        boolean is_resolved
        timestamp resolved_at
    }

    scheduler_jobs {
        uuid id PK
        string job_name UK
        string job_type
        text description
        int interval_seconds
        boolean is_enabled
        timestamp last_run_at
        timestamp next_run_at
        enum last_run_status
        int total_runs
        int successful_runs
        int failed_runs
    }

    scheduler_job_history {
        uuid id PK
        uuid job_id FK
        timestamp started_at
        timestamp completed_at
        int duration_ms
        enum status
        text error_message
        int items_processed
        jsonb run_metadata
    }

    sla_master_data {
        uuid id PK
        string reference_code UK
        string name
        decimal target_value
        decimal typical_performance
        string category
        string service_tower
        boolean is_active
    }

    milestone_master_data {
        uuid id PK
        string milestone_code UK
        string name
        int baseline_days_from_start
        jsonb dependencies
        decimal credit_at_risk
        boolean is_active
    }

    organizations {
        uuid id PK
        string name UK
        enum org_type
        string industry
        string size
        string region
        uuid relationship_owner_id FK
        boolean is_active
        timestamp created_at
    }

    business_relationships {
        uuid id PK
        uuid org_a_id FK
        uuid org_b_id FK
        enum relationship_type
        enum status
        int health_score
        uuid governance_model_id FK
        timestamp created_at
    }

    relationship_teams {
        uuid id PK
        uuid relationship_id FK
        uuid user_id FK
        string role
        jsonb responsibilities
        timestamp joined_at
    }

    kpis {
        uuid id PK
        uuid relationship_id FK
        string name
        text description
        enum measurement_type
        decimal target_value
        decimal threshold_amber
        decimal threshold_red
        boolean is_active
    }

    perception_scores {
        uuid id PK
        uuid kpi_id FK
        uuid scorer_org_id FK
        decimal score
        string period
        text comments
        uuid scored_by_user_id FK
        timestamp scored_at
    }

    perception_gaps {
        uuid id PK
        uuid kpi_id FK
        string period
        decimal internal_score
        decimal external_score
        decimal gap
        enum gap_severity
        timestamp calculated_at
    }

    improvement_points {
        uuid id PK
        uuid relationship_id FK
        uuid kpi_id FK
        uuid gap_id FK
        string title
        text description
        enum priority
        enum status
        uuid owner_id FK
        date due_date
        timestamp created_at
        timestamp completed_at
    }

    survey_templates {
        uuid id PK
        string name
        enum frequency
        boolean is_active
        timestamp created_at
    }

    survey_instances {
        uuid id PK
        uuid template_id FK
        uuid relationship_id FK
        string period
        enum status
        timestamp sent_at
        date due_date
    }

    survey_responses {
        uuid id PK
        uuid survey_id FK
        string respondent_email
        uuid respondent_org_id FK
        jsonb answers
        timestamp submitted_at
    }

    users {
        uuid id PK
        string email UK
        string hashed_password
        string full_name
        enum role
        boolean is_active
        timestamp last_login
    }

    audit_logs {
        uuid id PK
        uuid user_id FK
        enum action
        string resource_type
        uuid resource_id
        jsonb changes
        string ip_address
        timestamp created_at
    }
```

---

## 4. Sequence Diagrams

### 4.1 Contract Upload & Processing Flow

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant F as Frontend
    participant API as FastAPI
    participant Upload as UploadService
    participant Parser as ParserService
    participant Chunker as ChunkerService
    participant Indexer as IndexerService
    participant Agents as AI Agents
    participant LLM as OpenAI GPT-4o
    participant PG as PostgreSQL
    participant Chroma as ChromaDB
    participant FS as FileStorage

    U->>F: Select contract file(s)
    F->>API: POST /api/contracts/upload
    API->>Upload: validate_and_store()
    Upload->>FS: Save original file
    Upload->>PG: Create contract record (status=pending)
    Upload-->>API: contract_id
    API-->>F: {id, status: "pending"}
    F-->>U: Upload successful, processing...

    Note over API,Chroma: Background Processing Begins

    API->>Parser: parse_document(file_path)
    Parser->>Parser: Detect file type (PDF/DOCX)
    Parser->>Parser: Extract text with OCR fallback
    Parser-->>Indexer: Raw text + metadata

    Indexer->>Chunker: chunk_document(text)
    Chunker->>Chunker: Detect sections & clauses
    Chunker->>Chunker: Create semantic chunks (500 tokens)
    Chunker-->>Indexer: chunks[]

    Indexer->>Chroma: store_chunks(chunks, metadata)
    Chroma-->>Indexer: Embeddings stored

    par Agent Extraction
        Indexer->>Agents: MetadataExtractionAgent
        Agents->>LLM: Extract parties, dates, values
        LLM-->>Agents: Structured metadata
        Agents->>PG: Update contract metadata
    and
        Indexer->>Agents: RiskDetectionAgent
        Agents->>LLM: Assess risk factors
        LLM-->>Agents: risk_score, risk_level
        Agents->>PG: Update risk fields
    and
        Indexer->>Agents: ObligationExtractionAgent
        Agents->>LLM: Extract obligations
        LLM-->>Agents: obligations[]
        Agents->>PG: Create obligation records
    and
        Indexer->>Agents: ClauseExtractionAgent
        Agents->>LLM: Classify clauses
        LLM-->>Agents: clauses[]
        Agents->>PG: Create clause records
    end

    Indexer->>PG: Update contract (status=completed)

    Note over F,U: User polls for status or receives notification

    F->>API: GET /api/contracts/{id}
    API->>PG: Fetch contract with relations
    PG-->>API: Complete contract data
    API-->>F: Contract with metadata, clauses, obligations
    F-->>U: Display processed contract
```

### 4.2 Contract Q&A (RAG) Flow

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant F as Frontend
    participant API as FastAPI
    participant Orch as Orchestrator
    participant QA as ContractQAAgent
    participant Search as ContractSearchTool
    participant Chroma as ChromaDB
    participant LLM as OpenAI GPT-4o
    participant Langfuse as Langfuse

    U->>F: Enter question about contract
    F->>API: POST /api/query {question, contract_id?}

    API->>Langfuse: Start trace (user_id, session_id)
    API->>Orch: route_query(question)

    Orch->>Orch: Classify intent
    Orch->>QA: process(question, context)

    QA->>Search: search_contracts(query)
    Search->>Chroma: similarity_search(embedding, filters)

    Note over Search,Chroma: RBAC filtering applied<br/>based on user role

    Chroma-->>Search: relevant_chunks[]
    Search-->>QA: SearchResults with citations

    QA->>QA: Build context from chunks
    QA->>LLM: Generate response with sources

    Note over QA,LLM: System prompt includes:<br/>- Answer format requirements<br/>- Citation format<br/>- Follow-up suggestions

    LLM-->>QA: Response + reasoning

    QA->>QA: Extract citations from response
    QA->>QA: Generate follow-up suggestions

    QA-->>Orch: AgentOutput {answer, citations, suggestions}
    Orch->>Langfuse: End trace (tokens, latency, cost)
    Orch-->>API: Formatted response

    API-->>F: {answer, sources[], followups[]}
    F-->>U: Display answer with clickable sources

    opt User clicks source
        U->>F: Click citation link
        F->>API: GET /api/contracts/{id}/clauses/{clause_id}
        API-->>F: Clause detail with context
        F-->>U: Highlight source in document
    end

    opt User asks follow-up
        U->>F: Click suggested question
        Note over U,Langfuse: Flow repeats with same session_id
    end
```

### 4.3 SLA Comparison & Alert Flow

```mermaid
sequenceDiagram
    autonumber
    participant Scheduler as SchedulerService
    participant Job as SLAComparisonJob
    participant Engine as SLAComparisonEngine
    participant SNow as ServiceNowConnector
    participant PG as PostgreSQL
    participant Alert as SLAAlertService
    participant Notify as NotificationService
    participant Email as SMTP Server

    Note over Scheduler: Every 15 minutes (configurable)

    Scheduler->>Scheduler: Check due jobs
    Scheduler->>PG: Get enabled jobs where next_run_at <= now
    PG-->>Scheduler: sla_comparison job

    Scheduler->>Job: execute()
    Job->>PG: Create job_history (status=running)

    Job->>PG: Get active contracts with SLAs
    PG-->>Job: contracts[]

    loop For each contract
        Job->>Engine: compare_contract_slas(contract_id, date_range)

        Engine->>PG: Get contracted SLAs
        PG-->>Engine: contract_slas[]

        loop For each SLA
            Engine->>SNow: get_actual_performance(sla_code, date_range)

            alt Real ServiceNow
                SNow->>SNow: API call to ServiceNow
            else Stub Mode
                SNow->>SNow: Generate simulated data with variance
            end

            SNow-->>Engine: ActualPerformance {value, timestamp}

            Engine->>Engine: Calculate variance
            Engine->>Engine: Check breach thresholds

            Engine->>PG: Store sla_comparison_result

            alt Breach Detected
                Engine->>Alert: create_alert(breach_info)
                Alert->>PG: Create sla_alert record

                alt Critical Severity
                    Alert->>Notify: send_immediate_alert()
                    Notify->>PG: Get notification templates
                    Notify->>Notify: Render email template
                    Notify->>Email: Send alert email
                    Email-->>Notify: Delivery status
                    Notify->>PG: Log notification
                end
            end
        end

        Engine-->>Job: ComparisonSummary
    end

    Job->>PG: Update job_history (status=success, items_processed)
    Job->>PG: Update scheduler_job (next_run_at, stats)
    Job-->>Scheduler: Execution complete

    Note over Scheduler: Log execution metrics
```

### 4.4 Scheduled Job Execution Flow

```mermaid
sequenceDiagram
    autonumber
    participant Main as FastAPI Lifespan
    participant Svc as SchedulerService
    participant Loop as Scheduler Loop
    participant DB as PostgreSQL
    participant Executor as JobExecutor
    participant SLA as SLAComparisonJob

    Note over Main: Application Startup

    Main->>Svc: get_scheduler()
    Svc->>Svc: Create singleton instance
    Main->>Svc: start()

    Svc->>DB: Ensure default jobs exist
    DB-->>Svc: Jobs created/verified

    Svc->>Svc: Set is_running = True
    Svc->>Loop: Create asyncio task

    loop Every 10 seconds
        Loop->>Loop: Check is_running
        Loop->>DB: SELECT jobs WHERE enabled=true AND next_run_at <= now
        DB-->>Loop: due_jobs[]

        alt Jobs are due
            loop For each due job
                Loop->>Executor: create_task(execute_job)

                Executor->>DB: Mark job as RUNNING
                Executor->>DB: Create history entry

                alt job_name = "sla_comparison"
                    Executor->>SLA: execute(db_session)
                    SLA-->>Executor: {items_processed, metadata}
                else Unknown job
                    Executor->>Executor: Log warning
                end

                Executor->>DB: Calculate next_run_at
                Executor->>DB: Update job status, stats
                Executor->>DB: Update history entry
            end
        end

        Loop->>Loop: asyncio.sleep(10)
    end

    Note over Main: Application Shutdown

    Main->>Svc: stop()
    Svc->>Svc: Set is_running = False
    Svc->>Loop: Cancel task
    Loop-->>Svc: CancelledError caught
    Svc-->>Main: Scheduler stopped
```

### 4.5 User Authentication Flow

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant F as Frontend
    participant API as FastAPI
    participant Auth as AuthRouter
    participant Sec as SecurityService
    participant DB as PostgreSQL
    participant JWT as JWT Utils

    Note over U,F: Login Flow

    U->>F: Enter email + password
    F->>API: POST /api/auth/login
    API->>Auth: authenticate(email, password)

    Auth->>DB: SELECT user WHERE email = ?
    DB-->>Auth: User record

    alt User not found
        Auth-->>API: 401 Unauthorized
        API-->>F: Invalid credentials
        F-->>U: Show error
    else User found
        Auth->>Sec: verify_password(password, hashed)

        alt Password invalid
            Auth-->>API: 401 Unauthorized
            API-->>F: Invalid credentials
            F-->>U: Show error
        else Password valid
            Auth->>JWT: create_access_token(user_id, role)
            JWT-->>Auth: access_token (expires: 30min)
            Auth->>JWT: create_refresh_token(user_id)
            JWT-->>Auth: refresh_token (expires: 7days)

            Auth->>DB: Update last_login
            Auth-->>API: {access_token, refresh_token, user}
            API-->>F: Login successful
            F->>F: Store tokens in localStorage
            F-->>U: Redirect to dashboard
        end
    end

    Note over U,F: Authenticated Request

    U->>F: Navigate to protected page
    F->>F: Get token from localStorage
    F->>API: GET /api/contracts<br/>Authorization: Bearer {token}

    API->>Auth: Validate token (deps.py)
    Auth->>JWT: decode_token(token)

    alt Token expired
        JWT-->>Auth: TokenExpiredError
        Auth-->>API: 401 Token expired
        API-->>F: 401 Unauthorized
        F->>API: POST /api/auth/refresh<br/>{refresh_token}
        API->>JWT: Validate refresh token
        JWT-->>API: New access_token
        API-->>F: {access_token}
        F->>F: Update stored token
        F->>API: Retry original request
    else Token valid
        JWT-->>Auth: {user_id, role, exp}
        Auth->>DB: Get current user
        DB-->>Auth: User with permissions
        Auth-->>API: CurrentUser dependency
        API->>API: Check role permissions
        API-->>F: Protected resource
        F-->>U: Display content
    end

    Note over U,F: Logout Flow

    U->>F: Click logout
    F->>API: POST /api/auth/logout
    API->>Auth: Invalidate session
    Auth-->>API: Success
    API-->>F: Logged out
    F->>F: Clear localStorage
    F-->>U: Redirect to login
```

### 4.6 Workflow Execution Flow

```mermaid
sequenceDiagram
    autonumber
    participant Detector as EventDetector
    participant DB as PostgreSQL
    participant WF as WorkflowOrchestrator
    participant Handler as ActionHandler
    participant Approval as ApprovalService
    participant Notify as NotificationService
    participant User as Admin User

    Note over Detector: Periodic event detection (e.g., contract expiring)

    Detector->>DB: Check contracts for upcoming events
    DB-->>Detector: Contracts expiring in 30/60/90 days

    loop For each detected event
        Detector->>DB: Create Event record
        Detector->>DB: Find matching WorkflowDefinition
        DB-->>Detector: workflow_definition

        alt Workflow found
            Detector->>WF: trigger_workflow(event, workflow)

            WF->>DB: Get workflow steps (ordered)
            DB-->>WF: steps[]

            loop For each step
                WF->>WF: Check step conditions

                alt Step requires approval
                    WF->>Approval: create_request(step, approvers)
                    Approval->>DB: Create ApprovalRequest
                    Approval->>Notify: send_approval_notification()
                    Notify-->>User: Email: Approval needed

                    Note over Approval,User: Wait for approval

                    User->>DB: Approve/Reject request
                    DB-->>WF: Approval status

                    alt Rejected
                        WF->>DB: Log rejection, skip remaining steps
                        WF-->>Detector: Workflow terminated
                    end
                end

                alt Step is action
                    WF->>Handler: execute_action(step.action_type)

                    alt action = "send_notification"
                        Handler->>Notify: send(template, recipients)
                    else action = "create_task"
                        Handler->>DB: Create task record
                    else action = "update_status"
                        Handler->>DB: Update contract status
                    else action = "trigger_renewal"
                        Handler->>DB: Create renewal record
                    end

                    Handler->>DB: Log ActionExecution
                    Handler-->>WF: Action result
                end

                WF->>DB: Update step status
            end

            WF->>DB: Mark workflow complete
            WF-->>Detector: Workflow executed
        else No workflow
            Detector->>Detector: Log event, no action
        end
    end
```

### 4.7 Perception Scoring & Gap Analysis Flow

```mermaid
sequenceDiagram
    autonumber
    participant Int as Internal User
    participant Ext as External Stakeholder
    participant F as Frontend
    participant API as FastAPI
    participant Perc as PerceptionService
    participant Gap as GapCalculationService
    participant Notify as NotificationService
    participant DB as PostgreSQL

    Note over Int,F: Internal Perception Scoring

    Int->>F: Navigate to KPI scoring page
    F->>API: GET /api/relationships/{id}/kpis
    API->>DB: Fetch KPIs for relationship
    DB-->>API: KPIs with targets
    API-->>F: KPI list
    F-->>Int: Display KPI scoring form

    Int->>F: Submit internal scores (1-10 per KPI)
    F->>API: POST /api/kpis/{id}/scores
    API->>Perc: store_perception_score()
    Perc->>DB: Create PerceptionScore (scorer_org = internal)
    Perc-->>API: Score saved
    API-->>F: Success
    F-->>Int: Scores submitted

    Note over Ext,API: External Perception Scoring (Portal)

    Ext->>F: Access portal via token link
    F->>API: GET /api/external/{token}/context
    API->>DB: Validate token, get relationship + KPIs
    DB-->>API: Context data
    API-->>F: KPIs to score
    F-->>Ext: Display scoring form

    Ext->>F: Submit external scores
    F->>API: POST /api/external/{token}/scores
    API->>Perc: store_perception_score()
    Perc->>DB: Create PerceptionScore (scorer_org = external)

    Note over Perc,DB: Trigger Gap Calculation

    Perc->>Gap: calculate_gaps(kpi_id, period)
    Gap->>DB: Get internal + external scores
    DB-->>Gap: Both scores
    Gap->>Gap: Calculate gap = internal - external
    Gap->>Gap: Classify severity
    Gap->>DB: Store/Update PerceptionGap

    alt Gap severity >= significant
        Gap->>Notify: trigger_gap_alert()
        Notify->>DB: Get relationship owner
        Notify->>Notify: Send email notification
    end

    Gap-->>Perc: Gap calculated
    Perc-->>API: Score + gap saved
    API-->>F: Success with gap info
    F-->>Ext: Thank you page
```

### 4.8 Improvement Point Workflow

```mermaid
sequenceDiagram
    autonumber
    participant User as Account Manager
    participant F as Frontend
    participant API as FastAPI
    participant Imp as ImprovementService
    participant Health as HealthScoreService
    participant DB as PostgreSQL
    participant Notify as NotificationService

    Note over User,F: View Perception Gaps

    User->>F: View relationship dashboard
    F->>API: GET /api/relationships/{id}/perception-gaps
    API->>DB: Fetch gaps with severity
    DB-->>API: Gaps list
    API-->>F: Gaps with recommendations
    F-->>User: Display gaps (sorted by severity)

    Note over User,Imp: Create Improvement Point

    User->>F: Click "Create Improvement" on critical gap
    F-->>User: Display improvement form

    User->>F: Submit improvement point
    F->>API: POST /api/relationships/{id}/improvements
    API->>Imp: create_improvement()
    Imp->>DB: Create ImprovementPoint (linked to gap)
    Imp->>Notify: notify_stakeholders()
    Notify-->>Imp: Notifications sent
    Imp-->>API: Improvement created
    API-->>F: {improvement_id, status: "open"}
    F-->>User: Improvement created

    Note over User,DB: Update Progress

    User->>F: Update improvement status
    F->>API: PUT /api/improvements/{id}
    API->>Imp: update_improvement()
    Imp->>DB: Update status, add notes

    alt Status = completed
        Imp->>Health: recalculate_health_score()
        Health->>DB: Update relationship health score
    end

    Imp-->>API: Updated
    API-->>F: Success
    F-->>User: Status updated

    Note over API,DB: Add Action Items

    User->>F: Add action item to improvement
    F->>API: POST /api/improvements/{id}/actions
    API->>Imp: add_action()
    Imp->>DB: Create ImprovementAction
    Imp-->>API: Action created
    API-->>F: Action added
    F-->>User: Action visible in improvement
```

---

## 5. Data Flow Diagrams

### 5.1 Complete Data Pipeline

```mermaid
flowchart LR
    subgraph Input["Data Input"]
        Upload["Contract Upload<br/>PDF/DOCX/ZIP"]
        External["External Systems<br/>ServiceNow/Salesforce"]
        Manual["Manual Entry<br/>Admin UI"]
    end

    subgraph Processing["Processing Layer"]
        Parse["Document Parser<br/>Text Extraction"]
        Chunk["Semantic Chunker<br/>Section Detection"]
        AI["AI Agents<br/>Information Extraction"]
        Compare["Comparison Engine<br/>SLA Analysis"]
    end

    subgraph Storage["Storage Layer"]
        Vector[("ChromaDB<br/>Embeddings")]
        Relational[("PostgreSQL<br/>Structured Data")]
        Files[("File System<br/>Documents")]
    end

    subgraph Output["Output Layer"]
        Dashboard["Dashboards<br/>Analytics"]
        Alerts["Alerts<br/>Notifications"]
        Reports["Reports<br/>Exports"]
        API_Out["API<br/>Integrations"]
    end

    Upload --> Parse
    Parse --> Chunk
    Chunk --> Vector
    Chunk --> AI
    AI --> Relational
    Upload --> Files

    External --> Compare
    Compare --> Relational
    Compare --> Alerts

    Manual --> Relational

    Relational --> Dashboard
    Relational --> Reports
    Relational --> API_Out
    Vector --> Dashboard
    Alerts --> Output

    style Input fill:#E3F2FD
    style Processing fill:#FFF3E0
    style Storage fill:#E8F5E9
    style Output fill:#FCE4EC
```

### 5.2 Agent Orchestration Flow

```mermaid
flowchart TB
    subgraph Entry["Query Entry Points"]
        QA["Q&A Query"]
        Extract["Extraction Request"]
        Analyze["Analysis Request"]
    end

    subgraph Orchestrator["Agent Orchestrator"]
        Classify["Intent Classification"]
        Route["Agent Router"]
        Merge["Response Merger"]
    end

    subgraph Agents["Specialized Agents"]
        A1["Contract Q&A<br/>RAG + Citations"]
        A2["Metadata Agent<br/>Entity Extraction"]
        A3["Clause Agent<br/>Classification"]
        A4["Obligation Agent<br/>Tracking"]
        A5["Risk Agent<br/>Assessment"]
        A6["Renewal Agent<br/>Monitoring"]
        A7["SLA Agent<br/>Extraction"]
        A8["Schema Agent<br/>Custom Extraction"]
    end

    subgraph Tools["Agent Tools"]
        Search["ContractSearchTool<br/>Vector Search"]
        DB["DatabaseTool<br/>Structured Query"]
    end

    subgraph LLM["LLM Layer"]
        GPT["OpenAI GPT-4o"]
        Trace["Langfuse Tracing"]
    end

    Entry --> Classify
    Classify --> Route

    Route --> A1
    Route --> A2
    Route --> A3
    Route --> A4
    Route --> A5
    Route --> A6
    Route --> A7
    Route --> A8

    A1 --> Search
    A2 --> Search
    A3 --> Search
    A4 --> Search
    A5 --> Search
    A6 --> Search
    A7 --> Search
    A8 --> Search

    A1 --> DB
    A4 --> DB
    A5 --> DB

    Search --> GPT
    DB --> GPT
    GPT --> Trace

    A1 --> Merge
    A2 --> Merge
    A3 --> Merge
    A4 --> Merge
    A5 --> Merge
    A6 --> Merge
    A7 --> Merge
    A8 --> Merge

    Merge --> Entry

    style Orchestrator fill:#E1BEE7
    style Agents fill:#B3E5FC
    style Tools fill:#DCEDC8
    style LLM fill:#FFE0B2
```

### 5.3 Notification Flow

```mermaid
flowchart TB
    subgraph Triggers["Event Triggers"]
        SLA_Breach["SLA Breach<br/>Detected"]
        Contract_Exp["Contract<br/>Expiring"]
        Obligation_Due["Obligation<br/>Due"]
        Approval_Req["Approval<br/>Required"]
        System_Alert["System<br/>Alert"]
    end

    subgraph Service["Notification Service"]
        Queue["Event Queue"]
        Template["Template<br/>Engine"]
        Render["Message<br/>Renderer"]
        Dispatch["Dispatcher"]
    end

    subgraph Channels["Delivery Channels"]
        Email["Email<br/>SMTP"]
        Slack["Slack<br/>Webhook"]
        Webhook["Custom<br/>Webhook"]
        InApp["In-App<br/>Notification"]
    end

    subgraph Tracking["Delivery Tracking"]
        Log["Notification<br/>Log"]
        Retry["Retry<br/>Queue"]
        Status["Delivery<br/>Status"]
    end

    Triggers --> Queue
    Queue --> Template
    Template --> Render
    Render --> Dispatch

    Dispatch --> Email
    Dispatch --> Slack
    Dispatch --> Webhook
    Dispatch --> InApp

    Email --> Log
    Slack --> Log
    Webhook --> Log
    InApp --> Log

    Log --> Status
    Log -.-> Retry
    Retry -.-> Dispatch

    style Triggers fill:#FFCDD2
    style Service fill:#C8E6C9
    style Channels fill:#BBDEFB
    style Tracking fill:#F5F5F5
```

---

## 6. Deployment Architecture

```mermaid
flowchart TB
    subgraph Client["Client Tier"]
        Browser["Web Browser"]
        Mobile["Mobile App"]
    end

    subgraph CDN["CDN / Static"]
        Static["React Build<br/>Static Assets"]
    end

    subgraph LB["Load Balancer"]
        Nginx["Nginx<br/>Reverse Proxy"]
    end

    subgraph App["Application Tier"]
        subgraph Container1["Container 1"]
            FastAPI1["FastAPI<br/>Instance 1"]
        end
        subgraph Container2["Container 2"]
            FastAPI2["FastAPI<br/>Instance 2"]
        end
    end

    subgraph Data["Data Tier"]
        subgraph PG_Cluster["PostgreSQL"]
            PG_Primary[("Primary")]
            PG_Replica[("Replica")]
        end
        subgraph Chroma_Cluster["ChromaDB"]
            Chroma1[("Vector Store")]
        end
        subgraph Redis["Redis"]
            Cache[("Session Cache")]
        end
    end

    subgraph External["External Services"]
        OpenAI["OpenAI API"]
        Langfuse["Langfuse Cloud"]
        SMTP["SMTP Server"]
        ServiceNow["ServiceNow"]
        Salesforce["Salesforce"]
    end

    Client --> CDN
    CDN --> LB
    LB --> App

    FastAPI1 --> PG_Primary
    FastAPI2 --> PG_Primary
    PG_Primary --> PG_Replica

    FastAPI1 --> Chroma1
    FastAPI2 --> Chroma1

    FastAPI1 --> Cache
    FastAPI2 --> Cache

    App --> External

    style Client fill:#E3F2FD
    style App fill:#E8F5E9
    style Data fill:#FFF3E0
    style External fill:#FCE4EC
```

---

## 7. Security Architecture

```mermaid
flowchart TB
    subgraph External["External Access"]
        User["User"]
        API_Client["API Client"]
    end

    subgraph Security["Security Layer"]
        HTTPS["HTTPS/TLS"]
        CORS["CORS Policy"]
        RateLimit["Rate Limiting"]
    end

    subgraph Auth["Authentication"]
        JWT_Auth["JWT Validation"]
        Token_Refresh["Token Refresh"]
        Session["Session Management"]
    end

    subgraph Authz["Authorization"]
        RBAC["Role-Based Access"]
        Resource["Resource Ownership"]
        DataFilter["Data Filtering"]
    end

    subgraph Audit["Audit & Compliance"]
        AuditLog["Audit Logging"]
        Trace["Request Tracing"]
        Compliance["Compliance Reports"]
    end

    subgraph Data["Data Protection"]
        Encrypt["Encryption at Rest"]
        Hash["Password Hashing<br/>bcrypt"]
        Sanitize["Input Sanitization"]
    end

    External --> HTTPS
    HTTPS --> CORS
    CORS --> RateLimit
    RateLimit --> JWT_Auth
    JWT_Auth --> Token_Refresh
    Token_Refresh --> Session

    Session --> RBAC
    RBAC --> Resource
    Resource --> DataFilter

    DataFilter --> AuditLog
    AuditLog --> Trace
    Trace --> Compliance

    DataFilter --> Encrypt
    Auth --> Hash
    External --> Sanitize

    style Security fill:#FFCDD2
    style Auth fill:#C8E6C9
    style Authz fill:#BBDEFB
    style Audit fill:#E1BEE7
    style Data fill:#FFE0B2
```

---

*Diagrams created: 2026-02-12*
*Updated: 2026-02-16 - Updated router count (29), added FX connector, added Governance API group*
*Based on CLM codebase analysis*
*Render with any Mermaid-compatible viewer (GitHub, VS Code, etc.)*
