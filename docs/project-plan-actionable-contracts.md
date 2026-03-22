# Project Plan: Actionable Contracts

> Making contracts Transparent, Measurable, and **ACTIONABLE**

---

## Project Overview

| Attribute | Value |
|-----------|-------|
| **Project Name** | Evaluetor - Actionable Contract Management |
| **Goal** | Agents that detect events and execute actions autonomously |
| **Architecture** | Hybrid (Event-Driven + AgentSquad) |
| **Primary Scenario** | SLA Breach -> Calculation -> Approval -> Multi-Agent Execution |
| **Database** | PostgreSQL (existing) |
| **Status Tracking** | Database-driven task management |
| **Overall Status** | **8 of 10 phases complete** |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data Generation | Synthetic | Cover all test scenarios |
| Notifications | Email + Teams | Started simple, expanded to Teams webhooks |
| Approvals | Single approver + extensible | Flexibility for future |
| ServiceNow | Incidents + SLA metrics | Core use case |
| Salesforce | Account + Tasks | Visibility for account teams |
| Retry Logic | 3 attempts + graceful exit | Resilience without infinite loops |
| Monitoring | Real-time + On-demand | Flexibility for different needs |

---

## Phase 0: Planning & Setup -- COMPLETE
**Duration: Day 1**

### Tasks

| ID | Task | Description | Status |
|----|------|-------------|--------|
| 0.1 | Create project plan | This document | Complete |
| 0.2 | Design database schema | All new models | Complete |
| 0.3 | Create task tracking table | ProjectTask model | Complete |
| 0.4 | Set up project structure | New folders, packages | Complete |

### Deliverables
- [x] Project plan document (this file)
- [x] Database schema design
- [x] Task tracking in database (`ProjectTask`, `ProjectPhase`, `ProjectNote` models)
- [x] Folder structure for new components

---

## Phase 1: Core Models & Foundation -- COMPLETE
**Duration: Days 2-3**

### Tasks

| ID | Task | Description | Status |
|----|------|-------------|--------|
| 1.1 | Create Event model | Stores detected events | Complete |
| 1.2 | Create WorkflowDefinition model | Defines workflows per event type | Complete |
| 1.3 | Create WorkflowStep model | Steps within a workflow | Complete |
| 1.4 | Create ActionExecution model | Runtime execution tracking | Complete |
| 1.5 | Create ApprovalRequest model | Human-in-the-loop approvals | Complete |
| 1.6 | Create Approver model | Who can approve what | Complete |
| 1.7 | Create NotificationTemplate model | Email templates | Complete |
| 1.8 | Create NotificationLog model | Sent notifications | Complete |
| 1.9 | Create IntegrationConfig model | External system configs | Complete |
| 1.10 | Create IntegrationLog model | API call history | Complete |
| 1.11 | Create SLAMeasurement model | Synthetic SLA data | Complete |
| 1.12 | Run migrations | Apply all new models | Complete |
| 1.13 | Create seed data script | Initial workflows, templates | Complete |

### Deliverables
- [x] All database models created
- [x] Migrations applied (31 migration versions)
- [x] Seed data for workflows and templates

---

## Phase 2: Event Detection & Monitoring -- COMPLETE
**Duration: Days 4-5**

### Tasks

| ID | Task | Description | Status |
|----|------|-------------|--------|
| 2.1 | Create SLA measurement ingestion | Load synthetic SLA data | Complete |
| 2.2 | Create Monitor service | Scans for events | Complete |
| 2.3 | Implement SLA breach detection | Compare actual vs threshold | Complete |
| 2.4 | Implement milestone detection | Due dates approaching/overdue | Complete |
| 2.5 | Implement renewal detection | Renewal windows (90-day) | Complete |
| 2.6 | Create scheduler service | Async job executor | Complete |
| 2.7 | Create on-demand scan API | Manual trigger endpoint | Complete |
| 2.8 | Write monitor tests | Unit tests for detection | Partial |

### Key Files
- `app/workflows/event_detector.py` - `detect_sla_breaches()`, `detect_sla_warnings()`, `detect_renewal_approaching()`, `detect_milestones_overdue()`, `detect_obligations_due()`, `run_full_scan()`
- `app/workflows/monitor.py` - Dual-loop architecture (scan 300s + process 60s)
- `app/services/scheduler_service.py` - Singleton scheduler with job history
- `app/routers/monitor.py` - `POST /monitor/scan`, `POST /monitor/process`

### Deliverables
- [x] Monitor service detecting 5 event types
- [x] Scheduler running periodic scans
- [x] API for on-demand scanning
- [ ] Tests partially complete

---

## Phase 3: Workflow Engine -- COMPLETE
**Duration: Days 6-7**

### Tasks

| ID | Task | Description | Status |
|----|------|-------------|--------|
| 3.1 | Create WorkflowEngine service | Orchestrates workflow execution | Complete |
| 3.2 | Implement step sequencing | Execute steps in order | Complete |
| 3.3 | Implement approval checkpoints | Pause for human approval | Complete |
| 3.4 | Implement parallel execution | Multiple actions at once | Complete |
| 3.5 | Create approval API | Approve/reject endpoints | Complete |
| 3.6 | Create approval admin page API | List pending approvals | Complete |
| 3.7 | Write workflow tests | End-to-end workflow tests | Partial |

### Key Files
- `app/workflows/orchestrator.py` - Workflow execution orchestration
- `app/models/workflow.py` - WorkflowStep with `step_order`, `requires_approval`, `approval_timeout_hours`, `auto_approve_after_timeout`
- `app/routers/monitor.py` - `GET /monitor/approvals`, `POST /monitor/approvals/{id}/decide`

### Deliverables
- [x] Workflow engine processing events
- [x] Approval flow working (approve, reject, escalate, delegate)
- [x] Admin endpoints for approvals
- [ ] Tests partially complete

---

## Phase 4: Notification Service -- COMPLETE
**Duration: Days 8-9**

### Tasks

| ID | Task | Description | Status |
|----|------|-------------|--------|
| 4.1 | Create email service | SendGrid + SMTP integration | Complete |
| 4.2 | Create template renderer | Jinja2 for email templates | Complete |
| 4.3 | Implement NotificationService | Service that sends emails | Complete |
| 4.4 | Create approval request email | Template for approvals | Complete |
| 4.5 | Create SLA breach email | Template for vendor notification | Complete |
| 4.6 | Create failure notification | When actions fail after retries | Complete |
| 4.7 | Create notification history API | View sent notifications | Complete |
| 4.8 | Write notification tests | Email sending tests | Partial |

### Key Files
- `app/integrations/email.py` - SendGridClient + SMTPClient
- `app/services/notification_service.py` - NotificationService with Jinja2 TemplateRenderer, custom filters
- `app/routers/notifications.py` - History, statistics, retry endpoints

### Deliverables
- [x] Email service working (SendGrid + SMTP fallback)
- [x] All templates created (approval, breach, failure)
- [x] NotificationService with `send_notification()`, `send_event_notification()`, `send_approval_request_notification()`, `send_failure_notification()`
- [ ] Tests partially complete

---

## Phase 5: External Integrations -- COMPLETE
**Duration: Days 10-12**

### Tasks

| ID | Task | Description | Status |
|----|------|-------------|--------|
| 5.1 | Create base integration client | Retry logic, error handling | Complete |
| 5.2 | Implement ServiceNow client | Incident CRUD | Complete |
| 5.3 | Create ServiceNow action handler | Handler using SNOW client | Complete |
| 5.4 | Implement Salesforce client | Account update, Task create | Complete |
| 5.5 | Create Salesforce action handler | Handler using SFDC client | Complete |
| 5.6 | Create integration health check | Verify connectivity | Complete |
| 5.7 | Create integration admin API | Manage configs, view logs | Complete |
| 5.8 | Create mock servers | For testing without real APIs | Complete |
| 5.9 | Write integration tests | With mock servers | Partial |

### Key Files
- `app/integrations/base.py` - BaseIntegrationClient with retry, logging, MockIntegrationClient
- `app/integrations/servicenow.py` - Incident CRUD, work notes, resolution
- `app/integrations/salesforce.py` - OAuth2, account updates, tasks, SOQL queries
- `app/integrations/email.py` - SendGrid + SMTP
- `app/integrations/teams.py` - Microsoft Teams webhooks
- `app/routers/workflow_admin.py` - IntegrationConfig CRUD, IntegrationLog viewing

### Deliverables
- [x] ServiceNow integration working (real client + stub)
- [x] Salesforce integration working (real OAuth2 client)
- [x] Microsoft Teams webhook integration
- [x] Mock client for testing
- [x] Admin API for integration management
- [ ] Tests partially complete

---

## Phase 6: Calculation Agent -- COMPLETE
**Duration: Days 13-14**

### Tasks

| ID | Task | Description | Status |
|----|------|-------------|--------|
| 6.1 | Define calculation formulas | Service credits, penalties | Complete |
| 6.2 | Create CalculationService | Formula-based calculations | Complete |
| 6.3 | Implement service credit calc | Based on SLA breach severity | Complete |
| 6.4 | Store calculation results | In ActionExecution.result | Complete |
| 6.5 | Create calculation audit trail | Full breakdown of calculation | Complete |
| 6.6 | Write calculation tests | Verify formulas | Partial |

### Key Files
- `app/services/calculation_service.py` - `calculate_service_credit()`, `calculate_penalty()`, `get_credit_summary()`
- Supports: fixed, percentage, tiered, credit penalty types
- Formula evaluation with variables: deviation_percent, contract_value, credit_rate
- Cap enforcement and rounding

### Deliverables
- [x] CalculationService working with multiple formula types
- [x] Service credit calculation accurate (tiered + flat)
- [x] Audit trail for calculations (in ActionExecution.result)
- [ ] Tests partially complete

---

## Phase 7: Synthetic Data Generator -- NOT STARTED
**Duration: Days 15-16**

### Tasks

| ID | Task | Description | Status |
|----|------|-------------|--------|
| 7.1 | Create data generator service | Generates test scenarios | Not Started |
| 7.2 | Implement SLA data generator | Various performance levels | Not Started |
| 7.3 | Implement milestone generator | Due/overdue scenarios | Not Started |
| 7.4 | Implement renewal generator | Upcoming renewals | Not Started |
| 7.5 | Create scenario presets | Happy path, breach storm, etc. | Not Started |
| 7.6 | Create data generator API | Admin endpoint to generate | Not Started |
| 7.7 | Create data reset API | Clear and regenerate | Not Started |

### Note
Seed data scripts exist (`scripts/seed_data.py`, `scripts/seed_relationship_governance.py`) but a full synthetic data generator with scenario presets is not yet implemented.

### Deliverables
- [ ] Data generator working
- [ ] All scenario presets available
- [ ] Admin API for data management

---

## Phase 8: Admin Pages & APIs -- COMPLETE
**Duration: Days 17-19**

### Tasks

| ID | Task | Description | Status |
|----|------|-------------|--------|
| 8.1 | Create workflow management API | CRUD for workflows | Complete |
| 8.2 | Create approver management API | CRUD for approvers | Complete |
| 8.3 | Create template management API | CRUD for templates | Complete |
| 8.4 | Create event history API | View all events | Complete |
| 8.5 | Create action history API | View all executions | Complete |
| 8.6 | Create dashboard metrics API | Stats for admin dashboard | Complete |
| 8.7 | Create integration config API | Manage SNOW/SFDC configs | Complete |
| 8.8 | Create system health API | All services status | Complete |

### Key Files
- `app/routers/workflow_admin.py` - 19 endpoints for workflows, steps, approvers, templates, integrations
- `app/routers/monitor.py` - Events, actions, approvals, scan triggers
- `app/routers/scheduler_admin.py` - Job management, history, triggers
- `app/routers/dashboard.py` - 21 dashboard endpoints including admin view

### Deliverables
- [x] All admin APIs working (40+ endpoints)
- [x] Full visibility into system state
- [x] Management capabilities for all configs

---

## Phase 9: End-to-End Testing -- PARTIAL
**Duration: Days 20-21**

### Tasks

| ID | Task | Description | Status |
|----|------|-------------|--------|
| 9.1 | Create E2E test framework | Pytest fixtures for full flow | Complete |
| 9.2 | Test: SLA breach happy path | Full scenario execution | Not Started |
| 9.3 | Test: Approval rejection | Workflow stops correctly | Not Started |
| 9.4 | Test: Integration failure | Retry and graceful exit | Not Started |
| 9.5 | Test: Multiple events | Concurrent processing | Not Started |
| 9.6 | Test: Escalation timeout | Approval expires | Not Started |
| 9.7 | Performance testing | Load testing scheduler | Not Started |
| 9.8 | Create test report | Document all test results | Not Started |

### Current State
- E2E test directory exists (`/e2e/`)
- Playwright configuration at `/playwright.config.ts`
- Backend unit tests at `/backend/tests/` (conftest.py, test_auth.py, test_business_units.py, test_external_access.py)
- Testing guide at `docs/TESTING_GUIDE.md`

### Deliverables
- [x] E2E test framework set up
- [ ] Specific test scenarios not yet implemented
- [ ] Edge cases not covered
- [ ] Performance benchmarks not done

---

## Phase 10: Documentation & Handoff -- COMPLETE
**Duration: Day 22**

### Tasks

| ID | Task | Description | Status |
|----|------|-------------|--------|
| 10.1 | Update API documentation | OpenAPI/Swagger | Complete |
| 10.2 | Create architecture diagram | System overview | Complete |
| 10.3 | Create operations guide | How to run, monitor, troubleshoot | Complete |
| 10.4 | Create configuration guide | All settings explained | Complete |
| 10.5 | Update implementation matrix | Mark completed items | Complete |

### Key Files
- `docs/API_DOCUMENTATION.md` - ~305 endpoints documented
- `docs/ARCHITECTURE_OVERVIEW.md` - Full system architecture
- `docs/ARCHITECTURE_DIAGRAMS.md` - Mermaid sequence/flow diagrams
- `docs/DATA_MODEL.md` - Complete data model with ER diagrams
- `docs/TESTING_GUIDE.md` - Testing instructions
- `docs/implementation-matrix.md` - Updated to 89% completion
- `CLAUDE.md` - Developer onboarding guide

### Deliverables
- [x] Complete API documentation (~305 endpoints)
- [x] Architecture diagrams (ASCII + Mermaid)
- [x] Operations guide (Docker, deployment, seeding)
- [x] Updated implementation matrix

---

## Risk Register

| Risk | Impact | Mitigation | Status |
|------|--------|------------|--------|
| External API rate limits | Medium | Implement backoff, queue actions | Mitigated (retry logic in base client) |
| Email deliverability | Medium | Use reputable service (SendGrid) | Mitigated (SendGrid + SMTP fallback) |
| Approval bottleneck | High | Timeout with escalation | Mitigated (auto_approve_after_timeout + escalation) |
| Data consistency | High | Database transactions, idempotency | Mitigated (SQLAlchemy transactions) |
| Scheduler failure | High | Health checks, alerting | Mitigated (health API + auto-restart) |

---

## Success Criteria

| Criteria | Measurement | Status |
|----------|-------------|--------|
| SLA breach detected | Within 1 minute of data ingestion | Met (EventDetector) |
| Workflow completes | All steps execute in sequence | Met (WorkflowOrchestrator) |
| Approval works | Email sent, decision recorded | Met (ApprovalRequest + email) |
| Actions execute | SNOW incident + SFDC update created | Met (integration clients) |
| Failures handled | Retry 3x, then graceful exit with notification | Met (base client + failure notifications) |
| Audit complete | All actions traceable in Langfuse + DB | Met (Langfuse + AuditLog + ActionExecution) |

---

## Technology Stack

| Component | Technology | Status |
|-----------|------------|--------|
| Backend | FastAPI (existing) | Complete |
| Database | PostgreSQL (existing) | Complete |
| Scheduler | Async job executor (custom) | Complete |
| Email | SendGrid + SMTP | Complete |
| ServiceNow | REST API (real client) | Complete |
| Salesforce | REST API (OAuth2 client) | Complete |
| Microsoft Teams | Webhook API | Complete |
| Testing | Pytest + Playwright | Partial |

---

## Folder Structure (Implemented)

```
app/
|-- workflows/              # Workflow engine
|   |-- event_detector.py   # Event detection (5 types)
|   |-- monitor.py          # Dual-loop monitoring
|   +-- orchestrator.py     # Workflow execution
|-- actions/                # Action handlers
|   +-- handlers.py         # notify, servicenow, salesforce, calculate, escalate, webhook
|-- integrations/           # External clients
|   |-- base.py             # Base client with retry + MockClient
|   |-- servicenow.py       # SNOW API client
|   |-- salesforce.py       # SFDC OAuth2 client
|   |-- email.py            # SendGrid + SMTP
|   +-- teams.py            # Microsoft Teams webhooks
|-- generators/             # Synthetic data
|   +-- synthetic_data.py   # Data generators (basic)
|-- connectors/             # External system stubs
|   |-- servicenow_stub.py  # 19 SLA metric stubs
|   |-- milestone_stub.py   # 12 milestone stubs
|   +-- fx_stub.py          # FX rates + COLA calculations
|-- models/
|   |-- event.py            # Event + EventType + EventSeverity
|   |-- workflow.py         # WorkflowDefinition + WorkflowStep + ActionExecution
|   |-- approval.py         # Approver + ApprovalRequest
|   |-- notification.py     # NotificationTemplate + NotificationLog
|   |-- integration.py      # IntegrationConfig + IntegrationLog + SLAMeasurement
|   +-- ... (45 model files total)
+-- routers/
    |-- workflow_admin.py    # 19 workflow/approval/template/integration endpoints
    |-- monitor.py           # Events, scan, process, approvals
    |-- notifications.py     # Notification history, stats, retry
    |-- scheduler_admin.py   # Job management, history, triggers
    |-- connectors.py        # External connector + FX endpoints
    +-- ... (39 routers total)
```

---

*Plan created: 2026-02-10*
*Last updated: 2026-03-06*
