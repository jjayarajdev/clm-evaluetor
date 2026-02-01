# Contract Intelligence MVP

AI-powered Contract Lifecycle Management platform that extracts insights, identifies risks, and answers questions about your contracts.

## Features

- **Document Ingestion:** Upload PDF and DOCX contracts with automatic text extraction and OCR
- **Metadata Extraction:** Automatically extract contract type, parties, dates, values, and jurisdiction
- **Risk Detection:** Identify high-risk clauses and calculate contract risk scores
- **Obligation Tracking:** Extract and monitor contractual obligations with deadlines
- **Natural Language Q&A:** Ask questions about your contracts using RAG-powered AI
- **Role-Based Dashboards:** Tailored views for Admin, Legal, and Procurement users

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11+, FastAPI |
| Frontend | React, TypeScript |
| Database | PostgreSQL 15 |
| Vector Store | ChromaDB |
| AI/ML | OpenAI GPT-4o, Agent Squad |
| Observability | Langfuse |
| Package Manager | UV (Python), npm (Node) |
| Deployment | Docker Compose |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [UV](https://github.com/astral-sh/uv) (Python package manager)
- [Node.js](https://nodejs.org/) 18+ and npm
- OpenAI API key
- Langfuse account (optional, for observability)

## Quick Start

### 1. Clone and Configure

```bash
# Clone the repository
git clone <repository-url>
cd clm

# Copy environment template and configure
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Start Infrastructure

```bash
# Start PostgreSQL and ChromaDB
docker-compose up -d

# Verify services are running
docker-compose ps
```

### 3. Set Up Backend

```bash
cd backend

# Install dependencies with UV
uv sync

# Run database migrations
uv run alembic upgrade head

# Start the development server
uv run uvicorn app.main:app --reload --port 8000
```

### 4. Set Up Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

### 5. Access the Application

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/api/docs

## Project Structure

```
clm/
├── backend/                 # Python FastAPI backend
│   ├── app/
│   │   ├── agents/         # Agent Squad AI agents
│   │   ├── models/         # SQLAlchemy database models
│   │   ├── routers/        # API route handlers
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # Business logic
│   │   ├── config.py       # Application configuration
│   │   └── main.py         # FastAPI application
│   ├── alembic/            # Database migrations
│   └── pyproject.toml      # Python dependencies
├── frontend/               # React TypeScript frontend
│   ├── src/
│   │   ├── components/     # Reusable UI components
│   │   ├── pages/          # Page components
│   │   ├── hooks/          # Custom React hooks
│   │   └── services/       # API client
│   └── package.json        # Node dependencies
├── data/
│   ├── uploads/            # Uploaded contract files
│   └── processed/          # Processed contract files
├── docker-compose.yml      # Docker services configuration
├── .env.example            # Environment variables template
└── README.md               # This file
```

## Development

### Running Tests

```bash
# Backend tests
cd backend && uv run pytest

# Frontend tests
cd frontend && npm test
```

### Code Quality

```bash
# Backend linting
cd backend && uv run ruff check .

# Backend type checking
cd backend && uv run mypy app
```

### Database Migrations

```bash
cd backend

# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1
```

## Environment Variables

See `.env.example` for all available configuration options. Key variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4o | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `JWT_SECRET_KEY` | Secret for JWT token signing | Yes |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key | No |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key | No |

## License

Proprietary - All rights reserved.
