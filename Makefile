# Contract Intelligence Platform - Development Commands
.PHONY: help setup dev build start stop logs clean seed test lint

# Default target
help:
	@echo "Contract Intelligence Platform - Available Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make setup          - Initial setup (install deps, create .env)"
	@echo "  make install        - Install all dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make dev            - Start development environment (docker + local servers)"
	@echo "  make dev-backend    - Start backend only (requires docker DBs)"
	@echo "  make dev-frontend   - Start frontend only"
	@echo ""
	@echo "Docker:"
	@echo "  make build          - Build all Docker images"
	@echo "  make start          - Start full stack with Docker Compose"
	@echo "  make stop           - Stop all Docker containers"
	@echo "  make logs           - View Docker logs"
	@echo "  make clean          - Remove containers, volumes, and images"
	@echo ""
	@echo "Database:"
	@echo "  make db-up          - Start database containers only"
	@echo "  make db-migrate     - Run database migrations"
	@echo "  make db-seed        - Seed database with sample data"
	@echo "  make db-reset       - Reset database (drop, recreate, migrate, seed)"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test           - Run all tests"
	@echo "  make lint           - Run linters"
	@echo "  make format         - Format code"

# Setup
setup:
	@echo "Setting up development environment..."
	@test -f backend/.env || cp backend/.env.example backend/.env
	@test -f frontend/.env || echo "VITE_API_URL=http://localhost:8000" > frontend/.env
	@echo "Installing backend dependencies..."
	cd backend && uv sync
	@echo "Installing frontend dependencies..."
	cd frontend && npm install
	@echo ""
	@echo "Setup complete! Edit .env files with your configuration."
	@echo "Then run: make dev"

install:
	cd backend && uv sync
	cd frontend && npm install

# Development
dev: db-up
	@echo "Starting development servers..."
	@trap 'kill 0' EXIT; \
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 & \
	cd frontend && npm run dev & \
	wait

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

# Docker
build:
	docker compose build

start:
	docker compose up -d
	@echo "Services starting..."
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/api/docs"

stop:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down -v --rmi local
	@echo "Cleaned up containers, volumes, and images"

# Database
db-up:
	docker compose up -d postgres chromadb
	@echo "Waiting for databases to be ready..."
	@sleep 5

db-migrate:
	cd backend && uv run alembic upgrade head

db-seed:
	cd backend && uv run python -m scripts.seed_data

db-reset: db-up
	@echo "Resetting database..."
	docker compose exec postgres psql -U postgres -c "DROP DATABASE IF EXISTS contracts;"
	docker compose exec postgres psql -U postgres -c "CREATE DATABASE contracts;"
	@sleep 2
	cd backend && uv run alembic upgrade head
	cd backend && uv run python -m scripts.seed_data
	@echo "Database reset complete!"

# Testing
test:
	cd backend && uv run pytest -v
	cd frontend && npm run test

test-backend:
	cd backend && uv run pytest -v --cov=app

test-frontend:
	cd frontend && npm run test

# Linting & Formatting
lint:
	cd backend && uv run ruff check .
	cd frontend && npm run lint

format:
	cd backend && uv run ruff format .
	cd frontend && npm run format

# Aliases
up: start
down: stop
