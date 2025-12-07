#!/bin/bash
# =============================================================================
# setup-github-project.sh
# Creates and configures GitHub Project for Intelligent Trading Bot
# =============================================================================
# Prerequisites: GitHub CLI (gh) installed and authenticated
# Usage: ./scripts/setup-github-project.sh
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  GitHub Project Setup Script          ${NC}"
echo -e "${BLUE}  Intelligent Trading Bot              ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if gh is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) not installed${NC}"
    echo "Install: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${RED}Error: Not authenticated with GitHub CLI${NC}"
    echo "Run: gh auth login"
    exit 1
fi

# Get repo info - use remote origin URL to get correct repo (not upstream fork)
REPO=$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/' | sed 's/.*github.com[:/]\(.*\)/\1/')
OWNER=$(echo $REPO | cut -d'/' -f1)
echo -e "${GREEN}Repository: $REPO${NC}"
echo ""

# =============================================================================
# Step 1: Create Labels
# =============================================================================
echo -e "${YELLOW}Step 1: Creating labels...${NC}"

# Create labels using a simple approach (label|color|description)
LABELS="devops|d93f0b|Infrastructure, CI/CD, Terraform, Docker
feature|0e8a16|New functionality or enhancement
bug|b60205|Something isn't working
research|5319e7|R&D, ML experiments, analysis
infrastructure|fbca04|Cloud resources, Terraform
ml|d4c5f9|Machine Learning, models, training
pipeline|c2e0c6|Data pipeline, merge, features, labels
trading|006b75|Trading logic, signals, orders
config|bfd4f2|Configuration files, settings
priority-critical|b60205|Must be fixed ASAP
priority-high|d93f0b|Important, do soon
priority-medium|fbca04|Normal priority
priority-low|0e8a16|Nice to have
status-blocked|d73a4a|Blocked by something
status-in-progress|0052cc|Currently being worked on
status-review|fbca04|Ready for review
env-dev|c5def5|Development environment
env-staging|fef2c0|Staging environment
env-prod|f9d0c4|Production environment
documentation|0075ca|Documentation updates
experiment|d4c5f9|ML experiment, testing hypothesis
enhancement|a2eeef|Improvement to existing feature"

echo "$LABELS" | while IFS='|' read -r label color description; do
    echo -n "  Creating label '$label'... "
    if gh label create "$label" --color "$color" --description "$description" --repo "$REPO" 2>/dev/null; then
        echo -e "${GREEN}created${NC}"
    else
        echo -e "${YELLOW}exists${NC}"
    fi
done

echo ""

# =============================================================================
# Step 2: Create GitHub Project
# =============================================================================
echo -e "${YELLOW}Step 2: Creating GitHub Project...${NC}"

PROJECT_TITLE="Intelligent Trading Bot - Work Board"

# Check if project exists
EXISTING_PROJECT=$(gh project list --owner "$OWNER" --format json | jq -r ".projects[] | select(.title == \"$PROJECT_TITLE\") | .number" 2>/dev/null || echo "")

if [ -n "$EXISTING_PROJECT" ]; then
    echo -e "  Project already exists: #$EXISTING_PROJECT"
    PROJECT_NUMBER=$EXISTING_PROJECT
else
    echo -n "  Creating project... "
    PROJECT_NUMBER=$(gh project create --owner "$OWNER" --title "$PROJECT_TITLE" --format json | jq -r '.number')
    echo -e "${GREEN}created #$PROJECT_NUMBER${NC}"
fi

echo ""

# =============================================================================
# Step 3: Add Custom Fields
# =============================================================================
echo -e "${YELLOW}Step 3: Adding custom fields...${NC}"

# Work Type field
echo -n "  Adding 'Work Type' field... "
gh project field-create "$PROJECT_NUMBER" --owner "$OWNER" \
    --name "Work Type" \
    --data-type "SINGLE_SELECT" \
    --single-select-options "DevOps,Feature,Bug,R&D/ML" 2>/dev/null && echo -e "${GREEN}done${NC}" || echo -e "${YELLOW}exists${NC}"

# Priority field
echo -n "  Adding 'Priority' field... "
gh project field-create "$PROJECT_NUMBER" --owner "$OWNER" \
    --name "Priority" \
    --data-type "SINGLE_SELECT" \
    --single-select-options "Critical,High,Medium,Low" 2>/dev/null && echo -e "${GREEN}done${NC}" || echo -e "${YELLOW}exists${NC}"

# Environment field
echo -n "  Adding 'Environment' field... "
gh project field-create "$PROJECT_NUMBER" --owner "$OWNER" \
    --name "Environment" \
    --data-type "SINGLE_SELECT" \
    --single-select-options "dev,staging,prod" 2>/dev/null && echo -e "${GREEN}done${NC}" || echo -e "${YELLOW}exists${NC}"

# Sprint field
echo -n "  Adding 'Sprint' field... "
gh project field-create "$PROJECT_NUMBER" --owner "$OWNER" \
    --name "Sprint" \
    --data-type "ITERATION" 2>/dev/null && echo -e "${GREEN}done${NC}" || echo -e "${YELLOW}exists${NC}"

echo ""

# =============================================================================
# Step 4: Create Sample Issues
# =============================================================================
echo -e "${YELLOW}Step 4: Creating sample issues...${NC}"

# DevOps sample
echo -n "  Creating DevOps sample issue... "
DEVOPS_ISSUE=$(gh issue create --repo "$REPO" \
    --title "[DevOps] Setup monitoring and alerting" \
    --body "## Description
Setup monitoring for the trading bot infrastructure.

## Tasks
- [ ] Configure Azure Monitor
- [ ] Setup alerts for ACI failures
- [ ] Create dashboard for key metrics

## Environment
dev → staging → prod" \
    --label "devops" \
    --label "infrastructure" \
    --label "priority-medium" \
    --label "env-dev" 2>/dev/null | tail -1)
echo -e "${GREEN}$DEVOPS_ISSUE${NC}"

# Feature sample
echo -n "  Creating Feature sample issue... "
FEATURE_ISSUE=$(gh issue create --repo "$REPO" \
    --title "[Feature] Add support for ETHUSDT trading" \
    --body "## Description
Extend the trading bot to support ETHUSDT pair.

## Acceptance Criteria
- [ ] Config file for ETHUSDT
- [ ] Pipeline runs successfully
- [ ] Models trained and validated

## Technical Notes
Use same approach as BTCUSDT" \
    --label "feature" \
    --label "trading" \
    --label "priority-high" \
    --label "env-dev" 2>/dev/null | tail -1)
echo -e "${GREEN}$FEATURE_ISSUE${NC}"

# R&D sample
echo -n "  Creating R&D sample issue... "
RD_ISSUE=$(gh issue create --repo "$REPO" \
    --title "[R&D] Experiment with XGBoost vs LightGBM" \
    --body "## Hypothesis
XGBoost may perform better than LightGBM for 1m timeframe.

## Approach
1. Train both models on same dataset
2. Compare metrics (accuracy, precision, recall)
3. Backtest both strategies

## Success Metrics
- Accuracy improvement > 2%
- Sharpe ratio improvement

## Symbol
BTCUSDT

## Timeframe
1m" \
    --label "research" \
    --label "ml" \
    --label "experiment" \
    --label "priority-medium" 2>/dev/null | tail -1)
echo -e "${GREEN}$RD_ISSUE${NC}"

echo ""

# =============================================================================
# Step 5: Add Issues to Project
# =============================================================================
echo -e "${YELLOW}Step 5: Adding issues to project...${NC}"

for issue_url in "$DEVOPS_ISSUE" "$FEATURE_ISSUE" "$RD_ISSUE"; do
    if [ -n "$issue_url" ]; then
        echo -n "  Adding issue to project... "
        gh project item-add "$PROJECT_NUMBER" --owner "$OWNER" --url "$issue_url" 2>/dev/null && echo -e "${GREEN}done${NC}" || echo -e "${YELLOW}skipped${NC}"
    fi
done

echo ""

# =============================================================================
# Done!
# =============================================================================
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Setup Complete!                      ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Project URL: ${BLUE}https://github.com/orgs/$OWNER/projects/$PROJECT_NUMBER${NC}"
echo -e "             or: ${BLUE}https://github.com/users/$OWNER/projects/$PROJECT_NUMBER${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Open the project URL above"
echo -e "  2. Configure Board view with columns:"
echo -e "     Backlog → To Do → In Progress → Review → Done"
echo -e "  3. Enable automations:"
echo -e "     - Item closed → Move to Done"
echo -e "     - PR merged → Move to Done"
echo -e "  4. Start creating issues with the templates!"
echo ""
echo -e "${YELLOW}Tip: Run 'gh project view $PROJECT_NUMBER --owner $OWNER --web' to open in browser${NC}"
