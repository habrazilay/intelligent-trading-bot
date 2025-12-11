#!/bin/bash
#
# GCP Setup Script - Automated Setup for ITB Trading Bot
#
# This script will:
# 1. Install gcloud CLI (if needed)
# 2. Authenticate with your GCP account
# 3. Create a new project for ITB trading
# 4. Enable necessary APIs
# 5. Set up billing
# 6. Install Python dependencies
#
# Usage:
#   bash scripts/setup_gcp.sh
#

set -e  # Exit on error

echo "════════════════════════════════════════════════════════════"
echo "  GCP Setup for ITB Trading Bot"
echo "════════════════════════════════════════════════════════════"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if gcloud is installed
echo "1️⃣  Checking gcloud CLI installation..."
if ! command -v gcloud &> /dev/null; then
    echo -e "${YELLOW}gcloud CLI not found. Installing...${NC}"

    # Detect OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        echo "Detected macOS. Installing via curl..."
        curl https://sdk.cloud.google.com | bash
        exec -l $SHELL
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        echo "Detected Linux. Installing via package manager..."
        curl https://sdk.cloud.google.com | bash
        exec -l $SHELL
    else
        echo -e "${RED}Unsupported OS. Please install gcloud manually:${NC}"
        echo "https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
else
    echo -e "${GREEN}✓ gcloud CLI already installed${NC}"
    gcloud version
fi

echo ""
echo "2️⃣  Authenticating with GCP..."
echo "This will open a browser window for authentication."
read -p "Press ENTER to continue..."

gcloud auth login

echo ""
echo -e "${GREEN}✓ Authentication successful${NC}"

# Get user email
USER_EMAIL=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
echo "Logged in as: $USER_EMAIL"

echo ""
echo "3️⃣  Creating new GCP project for ITB Trading..."

# Generate unique project ID
TIMESTAMP=$(date +%s)
PROJECT_ID="itb-trading-${TIMESTAMP}"
PROJECT_NAME="ITB Trading Bot"

echo "Project ID: $PROJECT_ID"
echo "Project Name: $PROJECT_NAME"

# Create project
gcloud projects create $PROJECT_ID --name="$PROJECT_NAME"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Project created successfully${NC}"
else
    echo -e "${RED}✗ Failed to create project${NC}"
    exit 1
fi

# Set as active project
gcloud config set project $PROJECT_ID
echo -e "${GREEN}✓ Project set as active${NC}"

echo ""
echo "4️⃣  Setting up billing..."
echo ""
echo "Available billing accounts:"
gcloud billing accounts list

echo ""
echo "Please enter your billing account ID (format: 01XXXX-XXXXXX-XXXXXX):"
read BILLING_ACCOUNT_ID

# Link billing account
gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT_ID

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Billing account linked${NC}"
else
    echo -e "${RED}✗ Failed to link billing account${NC}"
    exit 1
fi

echo ""
echo "5️⃣  Enabling required APIs..."

# Enable APIs
APIS=(
    "aiplatform.googleapis.com"      # Vertex AI / AutoML
    "bigquery.googleapis.com"        # BigQuery
    "compute.googleapis.com"         # Compute Engine (for GPUs)
    "storage.googleapis.com"         # Cloud Storage
)

for API in "${APIS[@]}"; do
    echo "Enabling $API..."
    gcloud services enable $API
done

echo -e "${GREEN}✓ All APIs enabled${NC}"

echo ""
echo "6️⃣  Installing Python dependencies..."

# Check if in virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}Warning: Not in a virtual environment${NC}"
    echo "It's recommended to use a virtual environment."
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install GCP Python libraries
pip install --upgrade \
    google-cloud-aiplatform \
    google-cloud-bigquery \
    google-cloud-storage

echo -e "${GREEN}✓ Python dependencies installed${NC}"

echo ""
echo "7️⃣  Verifying setup..."

# Check project
CURRENT_PROJECT=$(gcloud config get-value project)
echo "Current project: $CURRENT_PROJECT"

# Check billing
BILLING_ENABLED=$(gcloud billing projects describe $PROJECT_ID --format="value(billingEnabled)")
echo "Billing enabled: $BILLING_ENABLED"

# Check enabled APIs
echo "Enabled APIs:"
gcloud services list --enabled --format="value(config.name)" | head -5

echo ""
echo "════════════════════════════════════════════════════════════"
echo -e "${GREEN}✓ GCP Setup Complete!${NC}"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📋 Summary:"
echo "   Project ID: $PROJECT_ID"
echo "   Project Name: $PROJECT_NAME"
echo "   Billing Account: $BILLING_ACCOUNT_ID"
echo "   User: $USER_EMAIL"
echo ""
echo "💰 Your Credits:"
echo "   View at: https://console.cloud.google.com/billing"
echo "   Estimated: ~\$970 USD available"
echo ""
echo "🚀 Next Steps:"
echo "   1. Finish orderbook collection (7 days)"
echo "   2. Run backtest locally"
echo "   3. If win rate ≥53% → Run AutoML"
echo ""
echo "Run AutoML with:"
echo "   python scripts/gcp_automl_train.py -c configs/btcusdt_5m_orderflow.jsonc --budget 1"
echo ""
echo "Monitor costs:"
echo "   python scripts/cloud_cost_monitor.py"
echo ""
echo "════════════════════════════════════════════════════════════"

# Save project info
cat > gcp_project_info.txt <<EOF
GCP Project Information
=======================

Created: $(date)
Project ID: $PROJECT_ID
Project Name: $PROJECT_NAME
Billing Account: $BILLING_ACCOUNT_ID
User: $USER_EMAIL

Enabled APIs:
- Vertex AI (aiplatform.googleapis.com)
- BigQuery (bigquery.googleapis.com)
- Compute Engine (compute.googleapis.com)
- Cloud Storage (storage.googleapis.com)

Quick Commands:
---------------
# Set project
gcloud config set project $PROJECT_ID

# Check billing
gcloud billing projects describe $PROJECT_ID

# List enabled APIs
gcloud services list --enabled

# Monitor costs
python scripts/cloud_cost_monitor.py

# Run AutoML
python scripts/gcp_automl_train.py -c configs/btcusdt_5m_orderflow.jsonc --budget 1
EOF

echo "Project info saved to: gcp_project_info.txt"
