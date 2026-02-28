#!/bin/bash
set -e

# CLM Platform Deployment Script
# Usage: ./deploy.sh [command]
# Commands: setup, deploy, logs, restart, stop, status

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check required tools
check_requirements() {
    log_info "Checking requirements..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    log_info "All requirements met."
}

# Setup environment
setup() {
    log_info "Setting up deployment environment..."

    cd "$SCRIPT_DIR"

    # Check if .env exists
    if [ ! -f .env ]; then
        log_warn ".env file not found. Creating from template..."
        cp .env.example .env

        # Generate secret key
        SECRET_KEY=$(openssl rand -hex 32)
        sed -i.bak "s/your_secret_key_here/$SECRET_KEY/" .env
        rm -f .env.bak

        log_warn "Please edit .env file and set:"
        log_warn "  - POSTGRES_PASSWORD (a secure password)"
        log_warn "  - OPENAI_API_KEY (your OpenAI API key)"
        log_warn "  - CORS_ORIGINS (add your EC2 public IP/domain)"
        echo ""
        log_info "Then run: ./deploy.sh deploy"
        exit 0
    fi

    # Validate required variables
    source .env

    if [ -z "$POSTGRES_PASSWORD" ] || [ "$POSTGRES_PASSWORD" = "your_secure_password_here" ]; then
        log_error "POSTGRES_PASSWORD not set in .env"
        exit 1
    fi

    if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "sk-..." ]; then
        log_error "OPENAI_API_KEY not set in .env"
        exit 1
    fi

    log_info "Environment validated."
}

# Deploy the application (preserves existing data)
deploy() {
    log_info "Starting deployment..."

    cd "$SCRIPT_DIR"
    setup

    # Check if this is a fresh deploy or update
    EXISTING_VOLUMES=$(docker volume ls -q | grep -E "deploy_postgres_data|deploy_chroma_data" | wc -l)

    if [ "$EXISTING_VOLUMES" -gt 0 ]; then
        log_info "Detected existing data volumes - this is an UPDATE deployment"
        log_info "Your PostgreSQL and ChromaDB data will be PRESERVED"
        SKIP_SEED=true
    else
        log_info "No existing volumes found - this is a FRESH deployment"
        SKIP_SEED=false
    fi

    # Build and start services
    log_info "Building Docker images..."
    docker compose -f docker-compose.prod.yml build

    log_info "Starting services..."
    docker compose -f docker-compose.prod.yml up -d

    # Wait for services to be healthy
    log_info "Waiting for services to be ready..."
    sleep 10

    # Run database migrations
    log_info "Running database migrations..."
    docker compose -f docker-compose.prod.yml exec -T backend alembic upgrade head || {
        log_warn "Migration failed, services may still be starting. Retrying in 10s..."
        sleep 10
        docker compose -f docker-compose.prod.yml exec -T backend alembic upgrade head
    }

    # Only seed on fresh deployments
    if [ "$SKIP_SEED" = false ]; then
        log_info "Seeding initial data (fresh deployment)..."
        docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.seed_data || true
        docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.seed_compliance_rules || true
    else
        log_info "Skipping seed data (existing deployment - data preserved)"
    fi

    log_info "Deployment complete!"
    echo ""
    status
}

# Force seed data (use with caution)
seed() {
    cd "$SCRIPT_DIR"
    log_warn "Seeding data - this will add demo data to the database"
    docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.seed_data || true
    docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.seed_compliance_rules || true
    log_info "Seeding complete."
}

# Show logs
logs() {
    cd "$SCRIPT_DIR"
    docker compose -f docker-compose.prod.yml logs -f "${1:-}"
}

# Restart services
restart() {
    cd "$SCRIPT_DIR"
    log_info "Restarting services..."
    docker compose -f docker-compose.prod.yml restart
    log_info "Services restarted."
}

# Stop services (preserves data volumes)
stop() {
    cd "$SCRIPT_DIR"
    log_info "Stopping services (data volumes will be PRESERVED)..."
    docker compose -f docker-compose.prod.yml down
    log_info "Services stopped. Data is safe in Docker volumes."
    log_info "To restart: ./deploy.sh deploy"
}

# Destroy everything including data (DANGEROUS!)
destroy() {
    cd "$SCRIPT_DIR"
    log_error "WARNING: This will DELETE ALL DATA including:"
    log_error "  - PostgreSQL database (all contracts, users, etc.)"
    log_error "  - ChromaDB vectors (all embeddings)"
    log_error "  - Uploaded files"
    echo ""
    read -p "Are you absolutely sure? Type 'DELETE ALL DATA' to confirm: " confirm
    if [ "$confirm" = "DELETE ALL DATA" ]; then
        log_warn "Removing all containers and volumes..."
        docker compose -f docker-compose.prod.yml down -v --remove-orphans
        log_info "All data has been deleted."
    else
        log_info "Cancelled. No data was deleted."
    fi
}

# Backup data volumes
backup() {
    cd "$SCRIPT_DIR"
    BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"

    log_info "Backing up PostgreSQL data..."
    docker compose -f docker-compose.prod.yml exec -T postgres pg_dumpall -U ${POSTGRES_USER:-clm} > "$BACKUP_DIR/postgres_backup.sql"

    log_info "Backing up ChromaDB data..."
    docker run --rm -v deploy_chroma_data:/data -v "$(pwd)/$BACKUP_DIR":/backup alpine tar czf /backup/chroma_backup.tar.gz -C /data .

    log_info "Backup complete: $BACKUP_DIR"
    ls -la "$BACKUP_DIR"
}

# Show status
status() {
    cd "$SCRIPT_DIR"
    echo ""
    log_info "Service Status:"
    docker compose -f docker-compose.prod.yml ps
    echo ""

    # Check if frontend is accessible
    if curl -s -o /dev/null -w "%{http_code}" http://localhost/health | grep -q "200"; then
        log_info "Frontend: ${GREEN}Healthy${NC}"
    else
        log_warn "Frontend: Not responding yet (may still be starting)"
    fi

    # Check if backend is accessible
    if curl -s http://localhost/api/health | grep -q "healthy\|degraded"; then
        log_info "Backend: ${GREEN}Healthy${NC}"
    else
        log_warn "Backend: Not responding yet (may still be starting)"
    fi

    echo ""
    log_info "Access the application at: http://$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_EC2_IP')"
}

# Main
case "${1:-}" in
    setup)
        check_requirements
        setup
        ;;
    deploy)
        check_requirements
        deploy
        ;;
    logs)
        logs "$2"
        ;;
    restart)
        restart
        ;;
    stop)
        stop
        ;;
    status)
        status
        ;;
    seed)
        seed
        ;;
    destroy)
        destroy
        ;;
    backup)
        backup
        ;;
    *)
        echo "CLM Platform Deployment"
        echo ""
        echo "Usage: $0 {setup|deploy|logs|restart|stop|status|seed|destroy|backup}"
        echo ""
        echo "Commands:"
        echo "  setup    - Initialize environment (creates .env from template)"
        echo "  deploy   - Build and start all services (preserves existing data)"
        echo "  logs     - Show logs (optional: service name)"
        echo "  restart  - Restart all services"
        echo "  stop     - Stop all services (preserves data volumes)"
        echo "  status   - Show service status"
        echo "  seed     - Manually seed demo data (use with caution)"
        echo "  backup   - Backup PostgreSQL and ChromaDB data"
        echo "  destroy  - DELETE ALL DATA (requires confirmation)"
        exit 1
        ;;
esac
