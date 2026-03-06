#!/bin/bash
# Quick AWS deployment script
# Usage: ./push-to-aws.sh <EC2_IP>

set -e

EC2_IP="${1:-}"
KEY_PATH="${2:-~/.ssh/clm-demo-key.pem}"

if [ -z "$EC2_IP" ]; then
    echo "Usage: $0 <EC2_IP> [SSH_KEY_PATH]"
    echo ""
    echo "Example: $0 54.123.45.67"
    echo "         $0 54.123.45.67 ~/.ssh/my-key.pem"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== CLM AWS Deployment ==="
echo "Target: ec2-user@$EC2_IP"
echo "Key: $KEY_PATH"
echo ""

# Expand tilde in key path
KEY_PATH="${KEY_PATH/#\~/$HOME}"

if [ ! -f "$KEY_PATH" ]; then
    echo "ERROR: SSH key not found: $KEY_PATH"
    exit 1
fi

# Test SSH connection
echo "[1/4] Testing SSH connection..."
ssh -i "$KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new ec2-user@$EC2_IP "echo 'SSH connection successful'" || {
    echo "ERROR: Cannot connect to $EC2_IP"
    exit 1
}

# Sync code (excluding unnecessary files)
echo "[2/4] Syncing code to AWS..."
rsync -avz --progress \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'node_modules' \
    --exclude '.venv' \
    --exclude '.env' \
    --exclude 'data/' \
    --exclude '*.sqlite*' \
    --exclude '.planning' \
    -e "ssh -i $KEY_PATH" \
    "$PROJECT_ROOT/" ec2-user@$EC2_IP:~/clm/

# Deploy
echo "[3/4] Running deployment on AWS..."
ssh -i "$KEY_PATH" ec2-user@$EC2_IP "cd ~/clm/deploy && ./deploy.sh deploy"

# Status
echo "[4/4] Checking deployment status..."
ssh -i "$KEY_PATH" ec2-user@$EC2_IP "cd ~/clm/deploy && ./deploy.sh status"

echo ""
echo "=== Deployment Complete ==="
echo "Access at: http://$EC2_IP"
echo ""
echo "Credentials:"
echo "  admin / admin123 (Acme Corp)"
echo "  legal / legal123 (Acme Corp)"
echo ""
