#!/usr/bin/env python3
"""Check project implementation progress.

Shows what components have been built for the Actionable Contracts system.
"""

import os
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).parent.parent


def check_file_exists(relative_path: str) -> bool:
    """Check if a file exists."""
    return (ROOT / relative_path).exists()


def check_files():
    """Check all implementation files."""

    components = {
        "Phase 1: Core Models": {
            "Event Model": "app/models/event.py",
            "Workflow Model": "app/models/workflow.py",
            "Approval Model": "app/models/approval.py",
            "Notification Model": "app/models/notification.py",
            "Integration Model": "app/models/integration.py",
            "Project Task Model": "app/models/project_task.py",
        },
        "Phase 2: Event Detection": {
            "Event Detector": "app/workflows/event_detector.py",
            "Monitor Service": "app/workflows/monitor.py",
        },
        "Phase 3: Workflow Engine": {
            "Workflow Orchestrator": "app/workflows/orchestrator.py",
        },
        "Phase 4: Notification Service": {
            "Notification Service": "app/services/notification_service.py",
            "Email Integration": "app/integrations/email.py",
        },
        "Phase 5: External Integrations": {
            "Base Client": "app/integrations/base.py",
            "ServiceNow Client": "app/integrations/servicenow.py",
            "Salesforce Client": "app/integrations/salesforce.py",
        },
        "Phase 6: Calculation Service": {
            "Calculation Service": "app/services/calculation_service.py",
        },
        "Phase 7: Synthetic Data": {
            "Data Generator": "app/generators/synthetic_data.py",
        },
        "Phase 8: Admin APIs": {
            "Monitor Router": "app/routers/monitor.py",
            "Workflow Admin Router": "app/routers/workflow_admin.py",
            "Notifications Router": "app/routers/notifications.py",
        },
        "Action Handlers": {
            "Action Handlers": "app/actions/handlers.py",
        },
        "AI Agents": {
            "SLA Extraction Agent": "app/agents/sla_extraction.py",
        },
        "Scripts": {
            "Seed Workflows": "scripts/seed_workflows.py",
            "Seed Project Tasks": "scripts/seed_project_tasks.py",
            "E2E Test": "scripts/test_workflow_e2e.py",
        },
        "Migrations": {
            "Workflow Migration": "alembic/versions/b1c2d3e4f5g6_add_workflow_models.py",
        },
    }

    print("=" * 60)
    print("ACTIONABLE CONTRACTS - IMPLEMENTATION PROGRESS")
    print("=" * 60)
    print()

    total_components = 0
    completed_components = 0

    for phase, files in components.items():
        print(f"\n{phase}")
        print("-" * 40)

        for name, path in files.items():
            total_components += 1
            exists = check_file_exists(path)
            if exists:
                completed_components += 1
                status = "[DONE]"
            else:
                status = "[    ]"
            print(f"  {status} {name}")

    print()
    print("=" * 60)
    print(f"TOTAL: {completed_components}/{total_components} components ({100*completed_components//total_components}%)")
    print("=" * 60)

    # Show API endpoints
    print("\nAPI ENDPOINTS AVAILABLE:")
    print("-" * 40)
    endpoints = [
        "POST /monitor/scan - Run event detection",
        "POST /monitor/process - Process workflows",
        "GET  /monitor/stats - View statistics",
        "GET  /monitor/events - List events",
        "GET  /monitor/approvals - List approvals",
        "POST /monitor/approvals/{id}/decide - Approve/reject",
        "GET  /monitor/workflows - List workflows",
        "POST /monitor/test-data - Generate test data",
        "POST /monitor/run-scenario - Run E2E scenario",
        "",
        "GET  /admin/workflows - List workflows",
        "POST /admin/workflows - Create workflow",
        "GET  /admin/templates - List templates",
        "POST /admin/templates - Create template",
        "GET  /admin/integrations - List integrations",
        "POST /admin/integrations/{id}/test - Test connection",
        "",
        "GET  /notifications - List notifications",
        "GET  /notifications/stats - Notification stats",
        "POST /notifications/{id}/retry - Retry failed",
        "POST /notifications/test - Send test email",
    ]

    for endpoint in endpoints:
        print(f"  {endpoint}")

    print()
    print("=" * 60)
    print("RUN TEST:")
    print("  python scripts/test_workflow_e2e.py")
    print("=" * 60)


if __name__ == "__main__":
    check_files()
