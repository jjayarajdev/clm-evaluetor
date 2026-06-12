"""Mock Enterprise Systems API.

Single FastAPI service mimicking Salesforce, Workday, SAP, ServiceNow,
Qualtrics, and Datadog APIs for CLM integration development and testing.

Port: 9000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.systems import salesforce, workday, sap, servicenow, qualtrics, datadog


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Mock Enterprise Systems",
    description=(
        "Simulates Salesforce, Workday, SAP, ServiceNow, Qualtrics, and Datadog APIs "
        "with realistic data tied to CLM entities. Use for integration development and demos."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all system routers
app.include_router(salesforce.router)
app.include_router(workday.router)
app.include_router(sap.router)
app.include_router(servicenow.router)
app.include_router(qualtrics.router)
app.include_router(datadog.router)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "systems": {
            "salesforce": {"prefix": "/api/sfdc", "endpoints": 8},
            "workday": {"prefix": "/api/workday", "endpoints": 8},
            "sap": {"prefix": "/api/sap", "endpoints": 8},
            "servicenow": {"prefix": "/api/snow", "endpoints": 8},
            "qualtrics": {"prefix": "/api/qualtrics", "endpoints": 6},
            "datadog": {"prefix": "/api/datadog", "endpoints": 10},
        },
    }


@app.get("/")
def root():
    return {
        "service": "Mock Enterprise Systems",
        "version": "0.1.0",
        "docs": "/docs",
        "systems": [
            {"name": "Salesforce", "prefix": "/api/sfdc", "description": "Accounts, Contacts, Opportunities"},
            {"name": "Workday", "prefix": "/api/workday", "description": "Workers, Organizations, Positions"},
            {"name": "SAP", "prefix": "/api/sap", "description": "Purchase Orders, Invoices, Payments"},
            {"name": "ServiceNow", "prefix": "/api/snow", "description": "SLA Results, Incidents, Changes"},
            {"name": "Qualtrics", "prefix": "/api/qualtrics", "description": "Surveys, Responses, Stats"},
            {"name": "Datadog", "prefix": "/api/datadog", "description": "Services, SLOs, Monitors, Incidents"},
        ],
    }
