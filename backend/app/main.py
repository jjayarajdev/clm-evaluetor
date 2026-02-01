from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, audit, contracts, dashboard, query, schemas, users
from app.services.vector_store import get_vector_store
from app.services.orchestrator import get_orchestrator, initialize_default_agents
from app.agents import register_all_agents
from app.schemas import get_schema_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup: Initialize agents and load schemas
    initialize_default_agents()
    register_all_agents()
    get_schema_registry().load_schemas()
    yield
    # Shutdown: Flush Langfuse
    orchestrator = get_orchestrator()
    orchestrator.flush()


app = FastAPI(
    title=settings.app_name,
    description="AI-powered Contract Intelligence Platform",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

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
app.include_router(users.router)
app.include_router(audit.router)
app.include_router(contracts.router)
app.include_router(query.router)
app.include_router(dashboard.router)
app.include_router(schemas.router)
