#!/bin/bash
#
# CLM Demo Setup Script
# ====================
# Sets up a complete demo environment with sample data.
#
# Usage:
#   cd backend
#   chmod +x scripts/setup_demo.sh
#   ./scripts/setup_demo.sh
#
# Prerequisites:
#   - PostgreSQL running (docker-compose up -d postgres)
#   - Python environment set up (uv sync)
#   - Backend not yet started (we'll start it)

set -e

echo "=============================================="
echo "CLM Demo Environment Setup"
echo "=============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the backend directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}Error: Please run this script from the backend directory${NC}"
    echo "  cd backend && ./scripts/setup_demo.sh"
    exit 1
fi

# Step 1: Database Setup
echo -e "${YELLOW}Step 1: Setting up database...${NC}"
echo "  Running migrations..."
uv run alembic upgrade head 2>/dev/null || {
    echo -e "${YELLOW}  Note: Some migrations may have already been applied${NC}"
}
echo -e "${GREEN}  Database ready${NC}"
echo ""

# Step 2: Seed Demo Data
echo -e "${YELLOW}Step 2: Seeding demo data...${NC}"
uv run python -m scripts.seed_demo
echo ""

# Step 3: Seed Workflows (if exists)
if [ -f "scripts/seed_workflows.py" ]; then
    echo -e "${YELLOW}Step 3: Seeding workflow definitions...${NC}"
    uv run python -m scripts.seed_workflows 2>/dev/null || {
        echo -e "${YELLOW}  Workflows may already exist${NC}"
    }
    echo ""
fi

# Step 4: Seed Relationship Governance (if exists)
if [ -f "scripts/seed_relationship_governance.py" ]; then
    echo -e "${YELLOW}Step 4: Seeding relationship governance data...${NC}"
    uv run python -m scripts.seed_relationship_governance 2>/dev/null || {
        echo -e "${YELLOW}  Relationship data may already exist${NC}"
    }
    echo ""
fi

echo "=============================================="
echo -e "${GREEN}Demo Setup Complete!${NC}"
echo "=============================================="
echo ""
echo "Next Steps:"
echo "  1. Start the backend:"
echo "     uv run uvicorn app.main:app --reload --port 8000"
echo ""
echo "  2. Start the frontend (in another terminal):"
echo "     cd frontend && npm run dev -- --port 3000"
echo ""
echo "  3. (Optional) Upload sample contracts:"
echo "     uv run python -m scripts.upload_sample_contracts"
echo ""
echo "Demo Credentials:"
echo "  admin@example.com / admin123"
echo "  sarah@example.com / legal123 (Legal role)"
echo "  mike@example.com  / proc123  (Procurement role)"
echo ""
echo "Open: http://localhost:3000"
echo ""
