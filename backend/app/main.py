from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware
from app.routers import (
    admin_settings, alerts, amendments, auth, audit, clients, connectors, contracts, dashboard,
    master_data_admin, metrics, milestones, monitor, notifications, obligations, postsigning, query,
    renewals, reports, scheduler_admin, schemas, sla, tenants, users, vendors, workflow_admin,
    # Relationship Governance (Evaluetor features)
    organizations, relationships, kpis, improvements, surveys,
)
from app.services.vector_store import get_vector_store
from app.services.orchestrator import get_orchestrator, initialize_default_agents
from app.services.langfuse_service import flush_langfuse
from app.services.scheduler_service import start_scheduler, stop_scheduler
from app.services.master_data_repository import auto_seed_master_data
from app.agents import register_all_agents
from app.schemas import get_schema_registry
from app.database import async_session_maker

# Configure logging before anything else
configure_logging(
    log_level=settings.log_level,
    json_output=settings.log_json,  # Configurable via LOG_JSON env var
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    logger.info("Application starting up", app_name=settings.app_name)

    # Startup: Initialize agents and load schemas
    initialize_default_agents()
    register_all_agents()
    get_schema_registry().load_schemas()

    # Auto-seed master data if not already seeded
    try:
        async with async_session_maker() as db:
            await auto_seed_master_data(db)
    except Exception as e:
        logger.warning(f"Auto-seed master data skipped: {e}")

    # Start the scheduler for background jobs
    try:
        await start_scheduler()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")

    logger.info("Application startup complete")
    yield

    # Shutdown
    logger.info("Application shutting down")

    # Stop the scheduler
    try:
        await stop_scheduler()
        logger.info("Scheduler stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")

    flush_langfuse()
    orchestrator = get_orchestrator()
    orchestrator.flush()
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.app_name,
    description="AI-powered Contract Intelligence Platform",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Add request logging middleware (must be added first to wrap all requests)
app.add_middleware(RequestLoggingMiddleware)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    vector_store = get_vector_store()
    orchestrator = get_orchestrator()

    chroma_healthy = vector_store.health_check()
    ai_health = await orchestrator.health_check()

    all_healthy = chroma_healthy and ai_health.get("openai", False)

    return {
        "status": "healthy" if all_healthy else "degraded",
        "version": "0.1.0",
        "services": {
            "chromadb": "healthy" if chroma_healthy else "unhealthy",
            "openai": "healthy" if ai_health.get("openai") else "unhealthy",
            "langfuse": "healthy" if ai_health.get("langfuse") else ("not_configured" if ai_health.get("langfuse") is None else "unhealthy"),
            "agents_registered": ai_health.get("agents_registered", 0),
        },
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Contract Intelligence API", "docs": "/api/docs"}


# Include routers
app.include_router(auth.router)
app.include_router(tenants.router)
app.include_router(users.router)
app.include_router(audit.router)
app.include_router(clients.router)
app.include_router(contracts.router)
app.include_router(amendments.router)
app.include_router(obligations.router)
app.include_router(sla.router)
app.include_router(renewals.router)
app.include_router(vendors.router)
app.include_router(milestones.router)
app.include_router(reports.router)
app.include_router(postsigning.router)
app.include_router(query.router)
app.include_router(dashboard.router)
app.include_router(schemas.router)
app.include_router(admin_settings.router)
app.include_router(monitor.router)
app.include_router(notifications.router)
app.include_router(workflow_admin.router)
app.include_router(connectors.router)
app.include_router(alerts.router)
app.include_router(master_data_admin.router)
app.include_router(scheduler_admin.router)
app.include_router(metrics.router)

# Relationship Governance (Evaluetor features)
app.include_router(organizations.router)
app.include_router(relationships.router)
app.include_router(kpis.router)
app.include_router(improvements.router)
app.include_router(surveys.router)
