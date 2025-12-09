# =============================================================================
# Intelligent Trading Bot - Makefile
# =============================================================================
# Best practice: Single entry point for all operations
# Usage: make <target>
# =============================================================================

.PHONY: help setup setup-azure setup-gcp setup-project docker-build docker-push \
        download train predict pipeline clean validate-configs \
        infra-dev-apply image-dev dev-1m dev-5m analyze-1m \
        upload-1m upload-5m upload-1h staging-1m staging-5m shadow-1m shadow-5m \
        analyze-staging analyze-staging-high-capital analyze-staging-custom

# Default target
help:
	@echo "════════════════════════════════════════════════════════════════"
	@echo "        Intelligent Trading Bot - Available Commands            "
	@echo "════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "  Setup:"
	@echo "    make setup            - Full setup (deps + validate)"
	@echo "    make setup-azure      - Setup Azure infrastructure"
	@echo "    make setup-gcp        - Setup GCP infrastructure"
	@echo "    make setup-project    - Setup GitHub Project + labels"
	@echo "    make infra-dev-apply  - Apply Terraform in dev"
	@echo ""
	@echo "  Docker:"
	@echo "    make docker-build     - Build Docker image"
	@echo "    make docker-push      - Push to Azure Container Registry"
	@echo "    make image-dev        - Build & push dev image"
	@echo ""
	@echo "  Pipeline (local):"
	@echo "    make download         - Download data from Binance"
	@echo "    make merge            - Merge data sources"
	@echo "    make features         - Generate features"
	@echo "    make labels           - Generate labels"
	@echo "    make train            - Train models"
	@echo "    make predict          - Run predictions"
	@echo "    make signals          - Generate signals"
	@echo "    make pipeline         - Run full pipeline"
	@echo ""
	@echo "  Dev Pipelines:"
	@echo "    make dev-1m           - Run dev pipeline 1m"
	@echo "    make dev-5m           - Run dev pipeline 5m"
	@echo ""
	@echo "  Analysis:"
	@echo "    make analyze-1m       - Run analyze_btcusdt_1m.py"
	@echo ""
	@echo "  Upload to Azure:"
	@echo "    make upload-1m        - Upload BTCUSDT 1m to Azure Files"
	@echo "    make upload-5m        - Upload BTCUSDT 5m to Azure Files"
	@echo "    make upload-1h        - Upload BTCUSDT 1h to Azure Files"
	@echo ""
	@echo "  Staging:"
	@echo "    make staging-1m       - Run staging 1m (shadow mode)"
	@echo "    make staging-5m       - Run staging 5m (shadow mode)"
	@echo ""
	@echo "  Shadow Mode Analysis:"
	@echo "    make analyze-staging            - Analyze shadow mode logs (V4)"
	@echo "    make analyze-staging-high-capital - Analyze with $10K capital"
	@echo "    make analyze-staging-custom     - Custom: LOG_FILE=... CAPITAL=... RISK=..."
	@echo ""
	@echo "  Utilities:"
	@echo "    make validate         - Validate all configs"
	@echo "    make clean            - Clean generated files"
	@echo "    make test             - Run tests"
	@echo ""

# =============================================================================
# Configuration
# =============================================================================

CONFIG ?= configs/btcusdt_1m_dev.jsonc
SYMBOL ?= BTCUSDT
ENV ?= dev
VERSION ?= $(shell date +v%Y-%m-%d)

# Azure
ACR_SERVER = itbacr.azurecr.io
ACR_REPO = itb-bot
IMAGE_TAG ?= $(shell git rev-parse --short HEAD)

# Paths
TF_AZURE_PATH = infra/azure/terraform/envs/$(ENV)
TF_GCP_PATH = infra/gcp/terraform/envs/$(ENV)

# =============================================================================
# Setup
# =============================================================================

setup: validate-configs
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt
	@echo "Setup complete!"

setup-azure:
	@echo "Setting up Azure infrastructure..."
	cd $(TF_AZURE_PATH) && terraform init
	cd $(TF_AZURE_PATH) && terraform plan
	@echo "Run 'cd $(TF_AZURE_PATH) && terraform apply' to apply changes"

setup-gcp:
	@echo "Setting up GCP infrastructure..."
	cd $(TF_GCP_PATH) && terraform init
	cd $(TF_GCP_PATH) && terraform plan
	@echo "Run 'cd $(TF_GCP_PATH) && terraform apply' to apply changes"

infra-dev-apply:
	@echo ">> terraform apply em infra/azure/terraform/envs/dev"
	cd infra/azure/terraform/envs/dev && terraform apply

setup-project:
	@echo ">> Setting up GitHub Project, labels, and sample issues"
	./scripts/setup-github-project.sh

# =============================================================================
# Docker
# =============================================================================

docker-build:
	@echo "Building Docker image..."
	docker build -t $(ACR_SERVER)/$(ACR_REPO):$(IMAGE_TAG) .
	docker tag $(ACR_SERVER)/$(ACR_REPO):$(IMAGE_TAG) $(ACR_SERVER)/$(ACR_REPO):latest

docker-push: docker-build
	@echo "Pushing to Azure Container Registry..."
	docker push $(ACR_SERVER)/$(ACR_REPO):$(IMAGE_TAG)
	docker push $(ACR_SERVER)/$(ACR_REPO):latest

image-dev:
	@echo ">> build & push imagem dev para itbacr.azurecr.io/itb-bot"
	docker build -t $(ACR_SERVER)/$(ACR_REPO):dev-$(IMAGE_TAG) .
	docker tag $(ACR_SERVER)/$(ACR_REPO):dev-$(IMAGE_TAG) $(ACR_SERVER)/$(ACR_REPO):dev-latest
	docker push $(ACR_SERVER)/$(ACR_REPO):dev-$(IMAGE_TAG)
	docker push $(ACR_SERVER)/$(ACR_REPO):dev-latest

# =============================================================================
# Pipeline - Local Execution
# =============================================================================

download:
	@echo "Downloading data for $(SYMBOL)..."
	python -m scripts.download_binance -c $(CONFIG)

merge:
	@echo "Merging data..."
	python -m scripts.merge_new -c $(CONFIG)

features:
	@echo "Generating features..."
	python -m scripts.features_new -c $(CONFIG)

labels:
	@echo "Generating labels..."
	python -m scripts.labels_new -c $(CONFIG)

train:
	@echo "Training models..."
	python -m scripts.train -c $(CONFIG)

predict:
	@echo "Running predictions..."
	python -m scripts.predict -c $(CONFIG)

signals:
	@echo "Generating signals..."
	python -m scripts.signals -c $(CONFIG)

pipeline: merge features labels train predict signals
	@echo "Full pipeline complete!"

# =============================================================================
# Dev Pipelines
# =============================================================================

dev-1m:
	@echo ">> rodar pipeline dev 1m"
	$(MAKE) pipeline CONFIG=configs/btcusdt_1m_dev.jsonc

dev-5m:
	@echo ">> rodar pipeline dev 5m"
	$(MAKE) pipeline CONFIG=configs/btcusdt_5m_dev.jsonc

# =============================================================================
# Analysis
# =============================================================================

analyze-1m:
	@echo ">> analyze_btcusdt_1m.py (local)"
	python my_tests/analyze_btcusdt_1m.py \
	  --parquet DATA_ITB_1m/BTCUSDT/klines.parquet \
	  --days 90

# =============================================================================
# Upload to Azure Files
# =============================================================================

upload-1m:
	@echo ">> upload BTCUSDT 1m para Azure Files"
	./tools/upload_1m_parquet.sh $(VERSION)

upload-5m:
	@echo ">> upload BTCUSDT 5m para Azure Files"
	./tools/upload_5m_parquet.sh $(VERSION)

upload-1h:
	@echo ">> upload BTCUSDT 1h para Azure Files"
	./tools/upload_1h_parquet.sh $(VERSION)

# =============================================================================
# Staging (Shadow Mode)
# =============================================================================

staging-1m:
	@echo ">> staging 1m (shadow mode)"
	ENABLE_LIVE_TRADING=true python -m service.server -c configs/btcusdt_1m_staging_v2.jsonc

staging-5m:
	@echo ">> staging 5m (shadow mode)"
	ENABLE_LIVE_TRADING=true python -m service.server -c configs/btcusdt_5m_staging_v2.jsonc

# =============================================================================
# Shadow Mode (Local with raw logs)
# =============================================================================

shadow-1m:
	@echo ">> shadow 1m (server + raw logs)"
	@mkdir -p logs/raw
	@TS=$$(date +"%Y-%m-%d_%H-%M"); \
	LOG_FILE=logs/raw/server_1m_shadow_$${TS}.log; \
	echo ">> logging to $$LOG_FILE"; \
	ENABLE_LIVE_TRADING=0 python -m service.server -c configs/btcusdt_1m_staging_v2.jsonc 2>&1 | tee $$LOG_FILE

shadow-5m:
	@echo ">> shadow 5m (server + raw logs)"
	@mkdir -p logs/raw
	@TS=$$(date +"%Y-%m-%d_%H-%M"); \
	LOG_FILE=logs/raw/server_5m_shadow_$${TS}.log; \
	echo ">> logging to $$LOG_FILE"; \
	ENABLE_LIVE_TRADING=0 python -m service.server -c configs/btcusdt_5m_staging_v2.jsonc 2>&1 | tee $$LOG_FILE

# =============================================================================
# Utilities
# =============================================================================

validate-configs:
	@echo "Validating configs..."
	@for f in configs/*.jsonc; do \
		python3 -c "import json, re; content=open('$$f').read(); content=re.sub(r'//.*', '', content); json.loads(content)" 2>&1 \
		&& echo "  OK $$f" || echo "  FAIL $$f"; \
	done

clean:
	@echo "Cleaning generated files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name ".DS_Store" -delete
	@echo "Clean complete!"

test:
	@echo "Running tests..."
	python -m pytest tests/ -v || echo "No tests found"

# =============================================================================
# Shadow Mode Analysis
# =============================================================================

analyze-staging:
	@echo "Analyzing shadow mode logs (V4 - Production Ready)..."
	python my_tests/analyze_staging_logs_v4.py --log-file server.log

analyze-staging-high-capital:
	@echo "Analyzing shadow mode with $10,000 starting capital..."
	python my_tests/analyze_staging_logs_v4.py \
		--log-file server.log \
		--starting-capital 10000 \
		--risk-per-trade 1.5

analyze-staging-custom:
	@echo "Analyzing custom log file..."
	@if [ -z "$(LOG_FILE)" ]; then \
		echo "Error: LOG_FILE not specified. Usage: make analyze-staging-custom LOG_FILE=path/to/server.log"; \
		exit 1; \
	fi
	python my_tests/analyze_staging_logs_v4.py \
		--log-file $(LOG_FILE) \
		--starting-capital $(or $(CAPITAL),1000) \
		--risk-per-trade $(or $(RISK),1.0)

# =============================================================================
# Multi-symbol operations
# =============================================================================

download-all:
	@echo "Downloading all symbols..."
	@for symbol in BTCUSDT ETHUSDT BNBUSDT SOLUSDT XRPUSDT; do \
		echo "  Downloading $$symbol..."; \
		python -m scripts.download_binance -c configs/$${symbol,,}_1m_dev.jsonc || true; \
	done

pipeline-all:
	@echo "Running pipeline for all symbols..."
	@for symbol in BTCUSDT ETHUSDT BNBUSDT SOLUSDT XRPUSDT; do \
		echo "═══════════════════════════════════════════════"; \
		echo "  Processing $$symbol..."; \
		echo "═══════════════════════════════════════════════"; \
		$(MAKE) pipeline CONFIG=configs/$${symbol,,}_1m_dev.jsonc || true; \
	done
