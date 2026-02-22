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

# Deploy the application
deploy() {
    log_info "Starting deployment..."

    cd "$SCRIPT_DIR"
    setup

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

    # Seed initial data
    log_info "Seeding initial data..."
    docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.seed_data || true
    docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.seed_compliance_rules || true

    log_info "Deployment complete!"
    echo ""
    status
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

# Stop services
stop() {
    cd "$SCRIPT_DIR"
    log_info "Stopping services..."
    docker compose -f docker-compose.prod.yml down
    log_info "Services stopped."
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
    *)
        echo "CLM Platform Deployment"
        echo ""
        echo "Usage: $0 {setup|deploy|logs|restart|stop|status}"
        echo ""
        echo "Commands:"
        echo "  setup    - Initialize environment (creates .env from template)"
        echo "  deploy   - Build and start all services"
        echo "  logs     - Show logs (optional: service name)"
        echo "  restart  - Restart all services"
        echo "  stop     - Stop all services"
        echo "  status   - Show service status"
        exit 1
        ;;
esac
