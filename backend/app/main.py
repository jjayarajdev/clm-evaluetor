import fcntl
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware
from app.routers import (
    admin_settings, alerts, amendments, auth, audit, clients, compliance, connectors, contracts,
    custom_fields, dashboard, knowledge_graph, master_data_admin, metrics, milestones, monitor,
    notifications, notification_rules, obligations, postsigning, query, renewals, reports,
    scheduler_admin, schemas, sla, suggested_links, tenants, users, vendors, workflow_admin,
    # Relationship Governance (Evaluetor features)
    organizations, relationships, kpis, improvements, surveys, service_portfolio,
    # Business Unit & External Access
    business_units, external_users, external_portal,
    # Contract Documents
    contract_documents,
    # Chat Sessions
    chat,
    # ServiceNow Integration
    snow_integration,
    # SharePoint Integration
    sharepoint_integration,
    # SSO (OIDC)
    sso,
    # Extraction Quality
    extraction_quality,
    # Industry Profiles (Multi-Domain CLM)
    industry_profiles,
    # Taxonomy Suggestions
    taxonomy_suggestions,
)
from app.services.vector_store import get_vector_store
from app.services.orchestrator import get_orchestrator, initialize_default_agents
from app.services.langfuse_service import flush_langfuse
from app.services.scheduler_service import start_scheduler, stop_scheduler
from app.services.processing_worker import start_processing_worker, stop_processing_worker
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

    # Start the scheduler on only one worker (file lock prevents duplicates)
    try:
        _scheduler_lock = open("/tmp/clm_scheduler.lock", "w")
        fcntl.flock(_scheduler_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        app.state._scheduler_lock = _scheduler_lock  # keep reference so GC doesn't release
        await start_scheduler()
        logger.info("Scheduler started successfully")

        # Start the processing worker alongside the scheduler
        await start_processing_worker()
        logger.info("Processing worker started successfully")
    except OSError:
        logger.info("Scheduler skipped (another worker owns it)")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")

    logger.info("Application startup complete")
    yield

    # Shutdown
    logger.info("Application shutting down")

    # Stop the scheduler
    try:
        await stop_processing_worker()
        await stop_scheduler()
        logger.info("Scheduler and processing worker stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler/worker: {e}")

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


@app.get("/api/system-health")
async def system_health():
    """Comprehensive system health with infrastructure metrics."""
    import psutil
    import os
    from datetime import datetime

    vector_store = get_vector_store()
    orchestrator = get_orchestrator()

    # Service health checks
    chroma_healthy = vector_store.health_check()
    ai_health = await orchestrator.health_check()

    # System metrics
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    # Process info
    process = psutil.Process()
    process_memory = process.memory_info()

    # Database connection check
    db_healthy = True
    db_stats = {}
    try:
        from app.database import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT count(*) FROM contracts"))
            contract_count = result.scalar()
            result = await conn.execute(text("SELECT pg_database_size(current_database())"))
            db_size = result.scalar()
            db_stats = {
                "contracts": contract_count,
                "database_size_mb": round(db_size / (1024 * 1024), 2) if db_size else 0,
            }
    except Exception as e:
        db_healthy = False
        db_stats = {"error": str(e)}

    # Vector store stats
    vector_stats = {}
    try:
        stats = vector_store.get_collection_stats()
        vector_stats = {
            "collection": stats.get("name", "unknown"),
            "document_count": stats.get("count", 0),
        }
    except Exception:
        vector_stats = {"error": "Failed to get vector store stats"}

    # Uptime
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime_seconds = (datetime.now() - boot_time).total_seconds()

    all_healthy = chroma_healthy and ai_health.get("openai", False) and db_healthy

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "environment": os.environ.get("ENVIRONMENT", "production"),
        "services": {
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
                "type": "PostgreSQL",
                **db_stats,
            },
            "chromadb": {
                "status": "healthy" if chroma_healthy else "unhealthy",
                "type": "Vector Store",
                **vector_stats,
            },
            "openai": {
                "status": "healthy" if ai_health.get("openai") else "unhealthy",
                "type": "LLM Provider",
            },
            "langfuse": {
                "status": "healthy" if ai_health.get("langfuse") else ("not_configured" if ai_health.get("langfuse") is None else "unhealthy"),
                "type": "Observability",
            },
        },
        "agents": {
            "registered": ai_health.get("agents_registered", 0),
        },
        "system": {
            "cpu_percent": cpu_percent,
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "percent": memory.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent": disk.percent,
            },
            "uptime_hours": round(uptime_seconds / 3600, 1),
        },
        "process": {
            "memory_mb": round(process_memory.rss / (1024**2), 2),
            "cpu_percent": process.cpu_percent(),
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
app.include_router(suggested_links.router)
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
app.include_router(custom_fields.router)
app.include_router(custom_fields.public_router)
app.include_router(monitor.router)
app.include_router(notifications.router)
app.include_router(notification_rules.router)
app.include_router(workflow_admin.router)
app.include_router(connectors.router)
app.include_router(alerts.router)
app.include_router(compliance.router)
app.include_router(master_data_admin.router)
app.include_router(scheduler_admin.router)
app.include_router(metrics.router)
app.include_router(knowledge_graph.router)
app.include_router(chat.router)

# Relationship Governance (Evaluetor features)
app.include_router(organizations.router)
app.include_router(relationships.router)
app.include_router(kpis.router)
app.include_router(improvements.router)
app.include_router(surveys.router)
app.include_router(service_portfolio.router)

# Contract Documents
app.include_router(contract_documents.router)

# Business Unit & External Access
app.include_router(business_units.router)
app.include_router(external_users.router)
app.include_router(external_portal.router)

# ServiceNow Integration
app.include_router(snow_integration.router)

# SharePoint Integration
app.include_router(sharepoint_integration.router)

# SSO (OIDC)
app.include_router(sso.router)

# Extraction Quality
app.include_router(extraction_quality.router)

# Industry Profiles (Multi-Domain CLM)
app.include_router(industry_profiles.router)

# Taxonomy Suggestions
app.include_router(taxonomy_suggestions.router)
