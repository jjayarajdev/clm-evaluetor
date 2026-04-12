#!/bin/bash
# ============================================================================
# AWS SES Setup Script for Evaluetor CLM
# ============================================================================
#
# This script sets up AWS SES for sending emails from the Evaluetor platform.
# Run this on the EC2 instance (52.21.204.211) or locally with AWS CLI configured.
#
# Prerequisites:
#   - AWS CLI installed and configured (aws configure)
#   - IAM user/role with SES permissions:
#       ses:SendEmail, ses:SendRawEmail, ses:GetSendQuota,
#       ses:VerifyEmailIdentity, ses:VerifyDomainIdentity,
#       ses:GetIdentityVerificationAttributes
#
# Usage:
#   # Full setup (verify email + configure DB + test):
#   ./setup-ses.sh setup
#
#   # Just verify a sender email:
#   ./setup-ses.sh verify-email notifications@evaluetor.com
#
#   # Just configure the database:
#   ./setup-ses.sh configure-db
#
#   # Check SES status:
#   ./setup-ses.sh status
#
#   # Send test email:
#   ./setup-ses.sh test recipient@example.com
#
#   # Request production access (out of sandbox):
#   ./setup-ses.sh request-production
#
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
FROM_EMAIL="${SES_FROM_EMAIL:-notifications@evaluetor.com}"
FROM_NAME="${SES_FROM_NAME:-Evaluetor CLM}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${CYAN}[STEP]${NC} $1"; }

# Determine docker compose command
get_compose_cmd() {
    if docker compose version &> /dev/null; then
        echo "docker compose"
    elif command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    else
        echo ""
    fi
}

# ── Check prerequisites ─────────────────────────────────────────────

check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not installed."
        echo "  Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        echo "  Or: sudo yum install -y awscli  (Amazon Linux)"
        exit 1
    fi

    # Check AWS credentials are configured
    if ! aws sts get-caller-identity &> /dev/null 2>&1; then
        log_error "AWS credentials not configured."
        echo "  Run: aws configure"
        echo "  Or set: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY environment variables"
        exit 1
    fi

    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    log_info "AWS Account: $ACCOUNT_ID"
    log_info "AWS Region: $REGION"
}

# ── SES Status ──────────────────────────────────────────────────────

ses_status() {
    log_step "Checking SES status..."

    echo ""
    echo "=== SES Send Quota ==="
    aws ses get-send-quota --region $REGION --output table 2>/dev/null || {
        log_error "Cannot access SES. Check IAM permissions."
        return 1
    }

    echo ""
    echo "=== Verified Identities ==="
    IDENTITIES=$(aws ses list-identities --region $REGION --output text 2>/dev/null)
    if [ -z "$IDENTITIES" ]; then
        log_warn "No verified identities. Run: $0 verify-email <email>"
    else
        for identity in $IDENTITIES; do
            STATUS=$(aws ses get-identity-verification-attributes \
                --identities "$identity" \
                --region $REGION \
                --query "VerificationAttributes.\"$identity\".VerificationStatus" \
                --output text 2>/dev/null)
            echo "  $identity: $STATUS"
        done
    fi

    echo ""
    echo "=== Send Statistics (last 24h) ==="
    aws ses get-send-statistics --region $REGION --output table 2>/dev/null | head -20

    # Check sandbox status
    QUOTA=$(aws ses get-send-quota --region $REGION --query 'Max24HourSend' --output text 2>/dev/null)
    if [ "$QUOTA" = "200" ] || [ "$QUOTA" = "200.0" ]; then
        echo ""
        log_warn "SES is in SANDBOX mode (200 emails/day limit)"
        log_warn "In sandbox, you can only send to verified email addresses."
        log_warn "Run: $0 request-production  to request production access."
    else
        echo ""
        log_info "SES is in PRODUCTION mode (quota: $QUOTA emails/day)"
    fi
}

# ── Verify Email Identity ───────────────────────────────────────────

verify_email() {
    local email="${1:-$FROM_EMAIL}"
    log_step "Verifying email identity: $email"

    aws ses verify-email-identity --email-address "$email" --region $REGION

    log_info "Verification email sent to $email"
    log_warn "Check inbox and click the verification link!"
    echo ""

    # Poll for verification (max 60 seconds)
    log_info "Waiting for verification (check your email)..."
    for i in {1..12}; do
        STATUS=$(aws ses get-identity-verification-attributes \
            --identities "$email" \
            --region $REGION \
            --query "VerificationAttributes.\"$email\".VerificationStatus" \
            --output text 2>/dev/null)

        if [ "$STATUS" = "Success" ]; then
            log_info "Email $email is VERIFIED!"
            return 0
        fi

        echo "  Status: $STATUS (attempt $i/12)..."
        sleep 5
    done

    log_warn "Email not yet verified. Click the link in your inbox, then run:"
    echo "  $0 status"
}

# ── Configure Database ──────────────────────────────────────────────

configure_db() {
    log_step "Configuring SES in application database..."

    local COMPOSE_CMD=$(get_compose_cmd)
    if [ -z "$COMPOSE_CMD" ]; then
        log_error "Docker Compose not found"
        exit 1
    fi

    cd "$SCRIPT_DIR"

    # Check if backend container is running
    if ! $COMPOSE_CMD -f docker-compose.prod.yml ps backend | grep -q "Up\|running"; then
        log_error "Backend container is not running. Start it first: ./deploy.sh deploy"
        exit 1
    fi

    # Get AWS credentials from environment or .env
    if [ -f .env ]; then
        source .env
    fi

    local ACCESS_KEY="${AWS_ACCESS_KEY_ID:-}"
    local SECRET_KEY="${AWS_SECRET_ACCESS_KEY:-}"
    local SES_REGION="${AWS_DEFAULT_REGION:-$REGION}"

    # Build the setup command
    local SETUP_CMD="python -m scripts.setup_ses --region $SES_REGION --from-email $FROM_EMAIL --from-name \"$FROM_NAME\""

    if [ -n "$ACCESS_KEY" ] && [ -n "$SECRET_KEY" ]; then
        SETUP_CMD="$SETUP_CMD --access-key $ACCESS_KEY --secret-key $SECRET_KEY"
    else
        SETUP_CMD="$SETUP_CMD --use-instance-role"
    fi

    # Run inside backend container
    $COMPOSE_CMD -f docker-compose.prod.yml exec -T backend $SETUP_CMD

    log_info "SES configured in database"
}

# ── Send Test Email ─────────────────────────────────────────────────

send_test() {
    local TO_EMAIL="${1:-}"
    if [ -z "$TO_EMAIL" ]; then
        log_error "Usage: $0 test <recipient@example.com>"
        exit 1
    fi

    log_step "Sending test email to $TO_EMAIL..."

    local COMPOSE_CMD=$(get_compose_cmd)
    if [ -z "$COMPOSE_CMD" ]; then
        # No Docker -- use AWS CLI directly
        log_info "Sending via AWS CLI..."
        aws ses send-email \
            --from "$FROM_NAME <$FROM_EMAIL>" \
            --destination "ToAddresses=$TO_EMAIL" \
            --message "Subject={Data=Evaluetor CLM - Test Email,Charset=UTF-8},Body={Html={Data='<html><body style=\"font-family:sans-serif;max-width:600px;margin:0 auto\"><div style=\"border-bottom:3px solid #7c3aed;padding-bottom:16px;margin-bottom:24px\"><h1 style=\"margin:0;color:#7c3aed\">Evaluetor</h1></div><p>This is a test email from your Evaluetor CLM platform.</p><p>If you received this, your AWS SES email integration is working correctly.</p><div style=\"border-top:1px solid #e5e7eb;margin-top:32px;padding-top:16px;color:#9ca3af;font-size:12px\">Sent by Evaluetor CLM</div></body></html>',Charset=UTF-8}}" \
            --region $REGION \
            --output text

        log_info "Test email sent to $TO_EMAIL via AWS CLI"
    else
        # Use Docker backend
        cd "$SCRIPT_DIR"
        $COMPOSE_CMD -f docker-compose.prod.yml exec -T backend \
            python -m scripts.setup_ses --test --to "$TO_EMAIL"
    fi
}

# ── Request Production Access ───────────────────────────────────────

request_production() {
    log_step "Requesting SES production access..."
    echo ""
    log_warn "This opens AWS Support Console to request production access."
    log_warn "You'll need to describe your use case (transactional emails for contract sharing)."
    echo ""
    echo "Go to: https://console.aws.amazon.com/ses/home?region=${REGION}#/account"
    echo ""
    echo "Or use AWS CLI:"
    echo "  aws sesv2 put-account-details \\"
    echo "    --production-access-enabled \\"
    echo "    --mail-type TRANSACTIONAL \\"
    echo "    --website-url https://evaluetor.com \\"
    echo "    --use-case-description 'Sending contract sharing invitations and governance dashboard access links to external business partners. Low volume, transactional only.' \\"
    echo "    --contact-language EN \\"
    echo "    --region $REGION"
    echo ""
    log_info "After approval (usually 24h), you can send to any email address."
}

# ── Full Setup ──────────────────────────────────────────────────────

full_setup() {
    log_step "=== Full SES Setup ==="
    echo ""

    check_aws_cli

    echo ""
    log_step "[1/4] Verifying sender email..."
    verify_email "$FROM_EMAIL"

    echo ""
    log_step "[2/4] Configuring database..."
    configure_db

    echo ""
    log_step "[3/4] Checking SES status..."
    ses_status

    echo ""
    log_step "[4/4] Setup complete!"
    echo ""
    echo "Next steps:"
    echo "  1. If SES is in sandbox mode, run: $0 request-production"
    echo "  2. Send a test email: $0 test your@email.com"
    echo "  3. In sandbox mode, verify recipient emails too: $0 verify-email recipient@example.com"
    echo ""
    echo "The invitation emails will now be sent when you share contracts"
    echo "or invite external users via the API or admin UI."
}

# ── Add AWS Credentials to .env ─────────────────────────────────────

setup_credentials() {
    log_step "Setting up AWS credentials in .env..."

    cd "$SCRIPT_DIR"

    if [ ! -f .env ]; then
        log_error ".env file not found. Run ./deploy.sh setup first."
        exit 1
    fi

    echo ""
    read -p "AWS Access Key ID: " ACCESS_KEY
    read -s -p "AWS Secret Access Key: " SECRET_KEY
    echo ""
    read -p "AWS Region [us-east-1]: " INPUT_REGION
    INPUT_REGION="${INPUT_REGION:-us-east-1}"
    read -p "Sender email [notifications@evaluetor.com]: " INPUT_EMAIL
    INPUT_EMAIL="${INPUT_EMAIL:-notifications@evaluetor.com}"

    # Add to .env if not already present
    if grep -q "AWS_ACCESS_KEY_ID" .env; then
        # Update existing
        sed -i.bak "s|^AWS_ACCESS_KEY_ID=.*|AWS_ACCESS_KEY_ID=$ACCESS_KEY|" .env
        sed -i.bak "s|^AWS_SECRET_ACCESS_KEY=.*|AWS_SECRET_ACCESS_KEY=$SECRET_KEY|" .env
        sed -i.bak "s|^AWS_DEFAULT_REGION=.*|AWS_DEFAULT_REGION=$INPUT_REGION|" .env
        rm -f .env.bak
    else
        # Append
        echo "" >> .env
        echo "# AWS SES Email" >> .env
        echo "AWS_ACCESS_KEY_ID=$ACCESS_KEY" >> .env
        echo "AWS_SECRET_ACCESS_KEY=$SECRET_KEY" >> .env
        echo "AWS_DEFAULT_REGION=$INPUT_REGION" >> .env
        echo "SES_FROM_EMAIL=$INPUT_EMAIL" >> .env
    fi

    log_info "AWS credentials saved to .env"
    log_warn "Restart backend to pick up new credentials:"
    echo "  docker compose -f docker-compose.prod.yml up -d --build backend"
}

# ── Main ────────────────────────────────────────────────────────────

case "${1:-}" in
    setup)
        full_setup
        ;;
    status)
        check_aws_cli
        ses_status
        ;;
    verify-email)
        check_aws_cli
        verify_email "${2:-}"
        ;;
    configure-db)
        configure_db
        ;;
    test)
        send_test "${2:-}"
        ;;
    request-production)
        request_production
        ;;
    credentials)
        setup_credentials
        ;;
    *)
        echo "Evaluetor CLM - AWS SES Email Setup"
        echo ""
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "Commands:"
        echo "  setup              Full setup (verify email + configure DB + status)"
        echo "  credentials        Interactive AWS credential setup (saves to .env)"
        echo "  status             Show SES status, quotas, and verified identities"
        echo "  verify-email <email>  Verify a sender email address"
        echo "  configure-db       Configure SES in application database"
        echo "  test <email>       Send a test email"
        echo "  request-production Request SES production access (out of sandbox)"
        echo ""
        echo "Environment:"
        echo "  AWS_DEFAULT_REGION  AWS region (default: us-east-1)"
        echo "  SES_FROM_EMAIL      Sender email (default: notifications@evaluetor.com)"
        echo "  SES_FROM_NAME       Sender name (default: Evaluetor CLM)"
        echo ""
        echo "Quick start:"
        echo "  $0 credentials      # Enter AWS keys interactively"
        echo "  $0 setup            # Verify email + configure everything"
        echo "  $0 test you@email.com  # Send a test"
        exit 1
        ;;
esac
