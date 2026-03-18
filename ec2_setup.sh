#!/bin/bash
# ec2_setup.sh — Run once on a fresh Amazon Linux 2023 EC2 instance
# Usage: bash ec2_setup.sh <aws-region> <ecr-registry>
# Example: bash ec2_setup.sh us-east-1 123456789.dkr.ecr.us-east-1.amazonaws.com

set -e

AWS_REGION=${1:-"us-east-1"}
ECR_REGISTRY=$2

echo "=== HR Agent EC2 Setup ==="
echo "Region: $AWS_REGION"

# ── 1. Update system ──────────────────────────────────────────
echo ""
echo "[1/6] Updating system packages..."
sudo dnf update -y

# ── 2. Install Docker ─────────────────────────────────────────
echo ""
echo "[2/6] Installing Docker..."
sudo dnf install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user
echo "Docker installed: $(docker --version)"

# ── 3. Install AWS CLI ────────────────────────────────────────
echo ""
echo "[3/6] Installing AWS CLI..."
sudo dnf install -y awscli
echo "AWS CLI installed: $(aws --version)"

# ── 4. Configure AWS region ───────────────────────────────────
echo ""
echo "[4/6] Configuring AWS region..."
aws configure set default.region $AWS_REGION
echo "AWS region set to: $AWS_REGION"

# ── 5. Create logs directory ──────────────────────────────────
echo ""
echo "[5/6] Creating app directories..."
mkdir -p /home/ec2-user/hr-agent/logs
chmod 755 /home/ec2-user/hr-agent/logs
echo "Logs directory: /home/ec2-user/hr-agent/logs"

# ── 6. Test ECR access ────────────────────────────────────────
echo ""
echo "[6/6] Testing ECR access..."
if [ -n "$ECR_REGISTRY" ]; then
    aws ecr get-login-password --region $AWS_REGION | \
        docker login --username AWS --password-stdin $ECR_REGISTRY \
        && echo "ECR login successful ✅" \
        || echo "ECR login failed — check IAM role permissions ❌"
else
    echo "ECR registry not provided — skipping ECR test"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Ensure the EC2 IAM role has these policies attached:"
echo "     - AmazonBedrockFullAccess (or scoped Bedrock policy)"
echo "     - AmazonEC2ContainerRegistryReadOnly"
echo ""
echo "  2. Add GitHub secrets to your repository:"
echo "     AWS_ACCESS_KEY_ID     — IAM user access key"
echo "     AWS_SECRET_ACCESS_KEY — IAM user secret key"
echo "     AWS_REGION            — e.g. us-east-1"
echo "     ECR_REGISTRY          — e.g. 123456789.dkr.ecr.us-east-1.amazonaws.com"
echo "     EC2_HOST              — EC2 public IP or DNS"
echo "     EC2_SSH_KEY           — contents of your .pem key file"
echo "     GITHUB_TOKEN          — GitHub personal access token"
echo "     LANGSMITH_API_KEY     — LangSmith API key"
echo ""
echo "  3. IMPORTANT: Log out and back in for docker group to take effect:"
echo "     exit"
echo "     ssh -i your-key.pem ec2-user@<ec2-host>"
echo ""
echo "  4. Push to main branch to trigger first deployment"