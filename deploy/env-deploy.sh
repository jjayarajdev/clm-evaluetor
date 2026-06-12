#!/bin/bash
# Multi-environment deploy wrapper.
#
# Usage:
#   ./env-deploy.sh staging         # deploy current code to staging
#   ./env-deploy.sh prod            # deploy current code to prod (extra confirmation)
#   ./env-deploy.sh staging --ssh   # SSH into the staging box
#   ./env-deploy.sh prod --status   # docker ps + alembic current on prod
#   ./env-deploy.sh prod --dump     # take a fresh pg_dump on prod, leave it on the box
#
# Reads target host + SSH key from ./environments.env (gitignored — copy from
# environments.env.example and fill in). Refuses to run if the env section is
# missing or empty. Always prints a big banner showing which env you're about
# to touch before doing anything destructive.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_CONFIG="$SCRIPT_DIR/environments.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }
info() { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }

usage() {
    cat <<EOF
Usage: $0 <env> [action]

Environments:
  prod      — production (the live AWS box)
  staging   — Lightsail staging box

Actions (default: deploy):
  deploy    — rsync code, run ./deploy.sh deploy, print status
  --ssh     — open an interactive SSH session
  --status  — show docker ps + alembic current
  --dump    — take a fresh pg_dump (custom format) into ~/clm-backups
  --logs    — tail backend logs

Examples:
  $0 staging              # deploy current code to staging
  $0 prod --status        # check what's running on prod
  $0 prod --dump          # snapshot DB before a deploy
EOF
}

ENV_NAME="${1:-}"
ACTION="${2:-deploy}"

if [ -z "$ENV_NAME" ] || [ "$ENV_NAME" = "-h" ] || [ "$ENV_NAME" = "--help" ]; then
    usage
    exit 0
fi

if [ ! -f "$ENV_CONFIG" ]; then
    err "Missing $ENV_CONFIG"
    echo
    echo "  Copy the template and fill in your values:"
    echo "    cp $SCRIPT_DIR/environments.env.example $ENV_CONFIG"
    echo
    exit 1
fi

# shellcheck disable=SC1090
source "$ENV_CONFIG"

case "$ENV_NAME" in
    prod)
        TARGET_IP="${PROD_IP:-}"
        TARGET_KEY="${PROD_KEY:-}"
        TARGET_ENV_FILE="${PROD_ENV_FILE:-}"
        ENV_DISPLAY="${RED}${BOLD}PRODUCTION${NC}"
        ;;
    staging)
        TARGET_IP="${STAGING_IP:-}"
        TARGET_KEY="${STAGING_KEY:-}"
        TARGET_ENV_FILE="${STAGING_ENV_FILE:-}"
        ENV_DISPLAY="${CYAN}${BOLD}STAGING${NC}"
        ;;
    *)
        err "Unknown environment '$ENV_NAME'. Expected 'prod' or 'staging'."
        exit 1
        ;;
esac

if [ -z "$TARGET_IP" ]; then
    ENV_UPPER=$(echo "$ENV_NAME" | tr '[:lower:]' '[:upper:]')
    err "$ENV_NAME has no IP configured in $ENV_CONFIG."
    echo "  Set ${ENV_UPPER}_IP=<your-ip> and try again."
    exit 1
fi

# Expand tilde in key path
TARGET_KEY="${TARGET_KEY/#\~/$HOME}"
if [ ! -f "$TARGET_KEY" ]; then
    err "SSH key not found: $TARGET_KEY"
    exit 1
fi

echo
echo -e "════════════════════════════════════════════════════════════"
echo -e " TARGET: $ENV_DISPLAY  ($ENV_NAME)"
echo -e " HOST:   ec2-user@$TARGET_IP"
echo -e " KEY:    $TARGET_KEY"
echo -e " ACTION: $ACTION"
echo -e "════════════════════════════════════════════════════════════"
echo

ssh_run() {
    ssh -i "$TARGET_KEY" -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
        ec2-user@"$TARGET_IP" "$@"
}

case "$ACTION" in
    deploy)
        # Extra friction for prod — staging deploys go through unprompted
        if [ "$ENV_NAME" = "prod" ]; then
            warn "About to deploy current local code to PROD."
            warn "Did you already test on staging? If not, this is your moment."
            read -p "Type 'DEPLOY PROD' to continue: " confirm
            if [ "$confirm" != "DEPLOY PROD" ]; then
                err "Aborted."
                exit 1
            fi
        fi
        # If the env config points at a local .env file, sync it to the box first
        if [ -n "$TARGET_ENV_FILE" ]; then
            TARGET_ENV_FILE="${TARGET_ENV_FILE/#\~/$HOME}"
            if [ ! -f "$TARGET_ENV_FILE" ]; then
                err ".env file referenced for $ENV_NAME does not exist: $TARGET_ENV_FILE"
                exit 1
            fi
            info "Syncing $TARGET_ENV_FILE → $ENV_NAME:~/clm/deploy/.env"
            scp -i "$TARGET_KEY" "$TARGET_ENV_FILE" ec2-user@"$TARGET_IP":~/clm/deploy/.env
        fi
        info "Handing off to push-to-aws.sh ..."
        exec "$SCRIPT_DIR/push-to-aws.sh" "$TARGET_IP" "$TARGET_KEY"
        ;;
    --ssh)
        info "Opening SSH session — exit with Ctrl-D."
        exec ssh -i "$TARGET_KEY" ec2-user@"$TARGET_IP"
        ;;
    --status)
        info "Running status check ..."
        ssh_run 'cd ~/clm/deploy && docker ps --format "table {{.Names}}\t{{.Status}}" \
                 && echo "---alembic---" \
                 && docker exec deploy-postgres-1 psql -U clm -d clm -c "SELECT version_num FROM alembic_version;"'
        ;;
    --dump)
        info "Taking pg_dump on $ENV_NAME ..."
        ssh_run '
            mkdir -p ~/clm-backups
            STAMP=$(date +%Y%m%d-%H%M%S)
            DUMPFILE=~/clm-backups/clm-'"$ENV_NAME"'-${STAMP}.dump
            docker exec deploy-postgres-1 pg_dump -U clm -d clm -Fc > "$DUMPFILE"
            ls -lh "$DUMPFILE"
        '
        ;;
    --logs)
        info "Tailing backend logs (Ctrl-C to exit) ..."
        ssh_run 'docker logs -f --tail=100 deploy-backend-1'
        ;;
    *)
        err "Unknown action '$ACTION'."
        usage
        exit 1
        ;;
esac
