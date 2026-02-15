#!/usr/bin/env python3
"""Seed project tasks from the project plan into the database."""

import asyncio
import sys
from pathlib import Path

# Add the app to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_session_maker
from app.models.project_task import (
    ProjectPhase,
    ProjectTask,
    TaskStatus,
    TaskPriority,
)


# Project phases and tasks from the project plan
PROJECT_DATA = {
    "phases": [
        {
            "phase_number": 0,
            "name": "Planning & Setup",
            "description": "Project plan, schema design, task tracking setup",
            "estimated_days": 1,
            "tasks": [
                {"id": "0.1", "name": "Create project plan", "desc": "This document", "priority": "high"},
                {"id": "0.2", "name": "Design database schema", "desc": "All new models for workflows, events, actions", "priority": "high"},
                {"id": "0.3", "name": "Create task tracking table", "desc": "ProjectTask model for progress tracking", "priority": "high"},
                {"id": "0.4", "name": "Set up project structure", "desc": "New folders: workflows, actions, integrations, generators", "priority": "medium"},
            ],
        },
        {
            "phase_number": 1,
            "name": "Core Models & Foundation",
            "description": "Database models for events, workflows, approvals, notifications, integrations",
            "estimated_days": 2,
            "tasks": [
                {"id": "1.1", "name": "Create Event model", "desc": "Stores detected events (SLA breach, milestone due, etc.)", "priority": "high"},
                {"id": "1.2", "name": "Create WorkflowDefinition model", "desc": "Defines workflows per event type", "priority": "high"},
                {"id": "1.3", "name": "Create WorkflowStep model", "desc": "Steps within a workflow", "deps": "1.2", "priority": "high"},
                {"id": "1.4", "name": "Create ActionExecution model", "desc": "Runtime execution tracking", "deps": "1.1,1.3", "priority": "high"},
                {"id": "1.5", "name": "Create ApprovalRequest model", "desc": "Human-in-the-loop approvals", "deps": "1.4", "priority": "high"},
                {"id": "1.6", "name": "Create Approver model", "desc": "Who can approve what workflows", "deps": "1.2", "priority": "medium"},
                {"id": "1.7", "name": "Create NotificationTemplate model", "desc": "Email templates with Jinja2", "priority": "medium"},
                {"id": "1.8", "name": "Create NotificationLog model", "desc": "History of sent notifications", "deps": "1.7", "priority": "medium"},
                {"id": "1.9", "name": "Create IntegrationConfig model", "desc": "External system configs (SNOW, SFDC)", "priority": "medium"},
                {"id": "1.10", "name": "Create IntegrationLog model", "desc": "API call history for debugging", "deps": "1.9", "priority": "medium"},
                {"id": "1.11", "name": "Create SLAMeasurement model", "desc": "Synthetic SLA performance data", "priority": "medium"},
                {"id": "1.12", "name": "Run migrations", "desc": "Apply all new models to database", "deps": "1.1,1.2,1.3,1.4,1.5,1.6,1.7,1.8,1.9,1.10,1.11", "priority": "high"},
                {"id": "1.13", "name": "Create seed data script", "desc": "Initial workflows, templates, and sample data", "deps": "1.12", "priority": "medium"},
            ],
        },
        {
            "phase_number": 2,
            "name": "Event Detection & Monitoring",
            "description": "Monitor service, scheduler, event detection logic",
            "estimated_days": 2,
            "tasks": [
                {"id": "2.1", "name": "Create SLA measurement ingestion", "desc": "Load synthetic SLA data into SLAMeasurement", "deps": "1.11", "priority": "high"},
                {"id": "2.2", "name": "Create Monitor service", "desc": "Scans contracts for actionable events", "deps": "1.1", "priority": "high"},
                {"id": "2.3", "name": "Implement SLA breach detection", "desc": "Compare actual vs threshold, create events", "deps": "2.1,2.2", "priority": "high"},
                {"id": "2.4", "name": "Implement milestone detection", "desc": "Due dates approaching or overdue", "deps": "2.2", "priority": "medium"},
                {"id": "2.5", "name": "Implement renewal detection", "desc": "Renewal windows opening", "deps": "2.2", "priority": "medium"},
                {"id": "2.6", "name": "Create scheduler service", "desc": "APScheduler for periodic scans", "deps": "2.2", "priority": "high"},
                {"id": "2.7", "name": "Create on-demand scan API", "desc": "Manual trigger endpoint for testing", "deps": "2.2", "priority": "medium"},
                {"id": "2.8", "name": "Write monitor tests", "desc": "Unit tests for all detection logic", "deps": "2.3,2.4,2.5", "priority": "medium"},
            ],
        },
        {
            "phase_number": 3,
            "name": "Workflow Engine",
            "description": "Orchestrate workflow execution, approvals, step sequencing",
            "estimated_days": 2,
            "tasks": [
                {"id": "3.1", "name": "Create WorkflowEngine service", "desc": "Orchestrates workflow execution from events", "deps": "1.2,1.3", "priority": "critical"},
                {"id": "3.2", "name": "Implement step sequencing", "desc": "Execute steps in defined order", "deps": "3.1", "priority": "high"},
                {"id": "3.3", "name": "Implement approval checkpoints", "desc": "Pause workflow for human approval", "deps": "3.1", "priority": "high"},
                {"id": "3.4", "name": "Implement parallel execution", "desc": "Multiple actions at same step", "deps": "3.1", "priority": "medium"},
                {"id": "3.5", "name": "Create approval API", "desc": "Approve/reject action executions", "deps": "1.5", "priority": "high"},
                {"id": "3.6", "name": "Create approval admin page API", "desc": "List pending approvals for user", "deps": "3.5", "priority": "medium"},
                {"id": "3.7", "name": "Write workflow tests", "desc": "End-to-end workflow execution tests", "deps": "3.1,3.2,3.3,3.4,3.5,3.6", "priority": "medium"},
            ],
        },
        {
            "phase_number": 4,
            "name": "Notification Service",
            "description": "Email service, templates, NotificationAgent",
            "estimated_days": 2,
            "tasks": [
                {"id": "4.1", "name": "Create email service", "desc": "SendGrid or SMTP integration", "priority": "high"},
                {"id": "4.2", "name": "Create template renderer", "desc": "Jinja2 for email templates", "deps": "1.7", "priority": "high"},
                {"id": "4.3", "name": "Implement NotificationAgent", "desc": "Action agent that sends emails", "deps": "4.1,4.2", "priority": "high"},
                {"id": "4.4", "name": "Create approval request email", "desc": "Template for approval notifications", "deps": "4.3", "priority": "medium"},
                {"id": "4.5", "name": "Create SLA breach email", "desc": "Template for vendor notification", "deps": "4.3", "priority": "medium"},
                {"id": "4.6", "name": "Create failure notification", "desc": "When actions fail after 3 retries", "deps": "4.3", "priority": "medium"},
                {"id": "4.7", "name": "Create notification history API", "desc": "View sent notifications", "deps": "1.8", "priority": "low"},
                {"id": "4.8", "name": "Write notification tests", "desc": "Email sending with mocks", "deps": "4.1,4.2,4.3,4.4,4.5,4.6", "priority": "medium"},
            ],
        },
        {
            "phase_number": 5,
            "name": "External Integrations",
            "description": "ServiceNow and Salesforce clients, action agents",
            "estimated_days": 3,
            "tasks": [
                {"id": "5.1", "name": "Create base integration client", "desc": "Retry logic, error handling, circuit breaker", "deps": "1.9", "priority": "high"},
                {"id": "5.2", "name": "Implement ServiceNow client", "desc": "Incident CRUD operations", "deps": "5.1", "priority": "high"},
                {"id": "5.3", "name": "Create ServiceNowAgent", "desc": "Action agent using SNOW client", "deps": "5.2", "priority": "high"},
                {"id": "5.4", "name": "Implement Salesforce client", "desc": "Account update, Task creation", "deps": "5.1", "priority": "high"},
                {"id": "5.5", "name": "Create SalesforceAgent", "desc": "Action agent using SFDC client", "deps": "5.4", "priority": "high"},
                {"id": "5.6", "name": "Create integration health check", "desc": "Verify connectivity to external systems", "deps": "5.1", "priority": "medium"},
                {"id": "5.7", "name": "Create integration admin API", "desc": "Manage configs, view logs", "deps": "1.9,1.10", "priority": "medium"},
                {"id": "5.8", "name": "Create mock servers", "desc": "For testing without real SNOW/SFDC", "deps": "5.2,5.4", "priority": "medium"},
                {"id": "5.9", "name": "Write integration tests", "desc": "Tests with mock servers", "deps": "5.8", "priority": "medium"},
            ],
        },
        {
            "phase_number": 6,
            "name": "Calculation Agent",
            "description": "Service credit calculations, financial logic",
            "estimated_days": 2,
            "tasks": [
                {"id": "6.1", "name": "Define calculation formulas", "desc": "Service credits, penalties based on SLA terms", "priority": "high"},
                {"id": "6.2", "name": "Create CalculationAgent", "desc": "LLM-assisted calculations with audit trail", "deps": "6.1", "priority": "high"},
                {"id": "6.3", "name": "Implement service credit calc", "desc": "Based on SLA breach severity and contract terms", "deps": "6.2", "priority": "high"},
                {"id": "6.4", "name": "Store calculation results", "desc": "In ActionExecution.result with breakdown", "deps": "6.2", "priority": "medium"},
                {"id": "6.5", "name": "Create calculation audit trail", "desc": "Full breakdown of calculation steps", "deps": "6.4", "priority": "medium"},
                {"id": "6.6", "name": "Write calculation tests", "desc": "Verify formulas with edge cases", "deps": "6.2,6.3,6.4,6.5", "priority": "medium"},
            ],
        },
        {
            "phase_number": 7,
            "name": "Synthetic Data Generator",
            "description": "Generate test scenarios for all obligation types",
            "estimated_days": 2,
            "tasks": [
                {"id": "7.1", "name": "Create data generator service", "desc": "Generates test scenarios on demand", "deps": "1.11", "priority": "high"},
                {"id": "7.2", "name": "Implement SLA data generator", "desc": "Various performance levels (green, amber, red)", "deps": "7.1", "priority": "high"},
                {"id": "7.3", "name": "Implement milestone generator", "desc": "Due, overdue, upcoming scenarios", "deps": "7.1", "priority": "medium"},
                {"id": "7.4", "name": "Implement renewal generator", "desc": "Upcoming renewals at various windows", "deps": "7.1", "priority": "medium"},
                {"id": "7.5", "name": "Create scenario presets", "desc": "Happy path, breach storm, renewal crunch, etc.", "deps": "7.1,7.2,7.3,7.4", "priority": "medium"},
                {"id": "7.6", "name": "Create data generator API", "desc": "Admin endpoint to generate data", "deps": "7.1", "priority": "medium"},
                {"id": "7.7", "name": "Create data reset API", "desc": "Clear synthetic data and regenerate", "deps": "7.6", "priority": "low"},
            ],
        },
        {
            "phase_number": 8,
            "name": "Admin Pages & APIs",
            "description": "Management APIs for all configurable entities",
            "estimated_days": 3,
            "tasks": [
                {"id": "8.1", "name": "Create workflow management API", "desc": "CRUD for workflow definitions and steps", "deps": "1.2,1.3", "priority": "high"},
                {"id": "8.2", "name": "Create approver management API", "desc": "CRUD for approvers per workflow", "deps": "1.6", "priority": "medium"},
                {"id": "8.3", "name": "Create template management API", "desc": "CRUD for notification templates", "deps": "1.7", "priority": "medium"},
                {"id": "8.4", "name": "Create event history API", "desc": "View all detected events with filters", "deps": "1.1", "priority": "medium"},
                {"id": "8.5", "name": "Create action history API", "desc": "View all action executions", "deps": "1.4", "priority": "medium"},
                {"id": "8.6", "name": "Create dashboard metrics API", "desc": "Stats for actionable contracts dashboard", "priority": "medium"},
                {"id": "8.7", "name": "Create integration config API", "desc": "Manage SNOW/SFDC connection settings", "deps": "1.9", "priority": "medium"},
                {"id": "8.8", "name": "Create system health API", "desc": "All services and integrations status", "priority": "low"},
            ],
        },
        {
            "phase_number": 9,
            "name": "End-to-End Testing",
            "description": "Full scenario testing and edge cases",
            "estimated_days": 2,
            "tasks": [
                {"id": "9.1", "name": "Create E2E test framework", "desc": "Pytest fixtures for full workflow testing", "priority": "high"},
                {"id": "9.2", "name": "Test: SLA breach happy path", "desc": "Full scenario from detection to actions", "deps": "9.1", "priority": "high"},
                {"id": "9.3", "name": "Test: Approval rejection", "desc": "Workflow stops correctly on rejection", "deps": "9.1", "priority": "medium"},
                {"id": "9.4", "name": "Test: Integration failure", "desc": "Retry 3x and graceful exit with notification", "deps": "9.1", "priority": "high"},
                {"id": "9.5", "name": "Test: Multiple events", "desc": "Concurrent event processing", "deps": "9.1", "priority": "medium"},
                {"id": "9.6", "name": "Test: Escalation timeout", "desc": "Approval expires and escalates", "deps": "9.1", "priority": "medium"},
                {"id": "9.7", "name": "Performance testing", "desc": "Load testing scheduler with many contracts", "deps": "9.1", "priority": "low"},
                {"id": "9.8", "name": "Create test report", "desc": "Document all test results", "deps": "9.2,9.3,9.4,9.5,9.6,9.7", "priority": "low"},
            ],
        },
        {
            "phase_number": 10,
            "name": "Documentation & Handoff",
            "description": "Complete documentation and cleanup",
            "estimated_days": 1,
            "tasks": [
                {"id": "10.1", "name": "Update API documentation", "desc": "OpenAPI/Swagger for all new endpoints", "priority": "high"},
                {"id": "10.2", "name": "Create architecture diagram", "desc": "System overview with all components", "priority": "medium"},
                {"id": "10.3", "name": "Create operations guide", "desc": "How to run, monitor, troubleshoot", "priority": "medium"},
                {"id": "10.4", "name": "Create configuration guide", "desc": "All settings and environment variables", "priority": "medium"},
                {"id": "10.5", "name": "Update implementation matrix", "desc": "Mark all completed items", "priority": "low"},
            ],
        },
    ]
}


async def seed_project_tasks():
    """Seed project phases and tasks into the database."""
    async with async_session_maker() as db:
        # Check if already seeded
        from sqlalchemy import select, func
        result = await db.execute(select(func.count(ProjectPhase.id)))
        count = result.scalar()

        if count > 0:
            print(f"Project tasks already seeded ({count} phases found). Skipping.")
            print("To re-seed, delete existing data first.")
            return

        print("Seeding project phases and tasks...")

        priority_map = {
            "low": TaskPriority.low,
            "medium": TaskPriority.medium,
            "high": TaskPriority.high,
            "critical": TaskPriority.critical,
        }

        for phase_data in PROJECT_DATA["phases"]:
            # Create phase
            phase = ProjectPhase(
                phase_number=phase_data["phase_number"],
                name=phase_data["name"],
                description=phase_data["description"],
                estimated_days=phase_data["estimated_days"],
                status=TaskStatus.not_started,
            )
            db.add(phase)
            await db.flush()  # Get the phase ID

            # Create tasks
            for task_data in phase_data["tasks"]:
                task = ProjectTask(
                    phase_id=phase.id,
                    task_id=task_data["id"],
                    name=task_data["name"],
                    description=task_data.get("desc", ""),
                    status=TaskStatus.not_started,
                    priority=priority_map.get(task_data.get("priority", "medium"), TaskPriority.medium),
                    dependencies=task_data.get("deps"),
                )
                db.add(task)

            print(f"  Phase {phase_data['phase_number']}: {phase_data['name']} ({len(phase_data['tasks'])} tasks)")

        await db.commit()
        print("\nProject tasks seeded successfully!")

        # Print summary
        result = await db.execute(select(func.count(ProjectTask.id)))
        task_count = result.scalar()
        print(f"Total: {len(PROJECT_DATA['phases'])} phases, {task_count} tasks")


if __name__ == "__main__":
    asyncio.run(seed_project_tasks())
