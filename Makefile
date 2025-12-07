# =============================================================================
# Intelligent Trading Bot - Makefile
# =============================================================================
# Best practice: Single entry point for all operations
# Usage: make <target>
# =============================================================================

.PHONY: help setup setup-azure setup-gcp docker-build docker-push \
        download train predict pipeline clean validate-configs

# Default target
help:
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║        Intelligent Trading Bot - Available Commands            ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "  Setup:"
	@echo "    make setup          - Full setup (deps + validate)"
	@echo "    make setup-azure    - Setup Azure infrastructure"
	@echo "    make setup-gcp      - Setup GCP infrastructure"
	@echo ""
	@echo "  Docker:"
	@echo "    make docker-build   - Build Docker image"
	@echo "    make docker-push    - Push to Azure Container Registry"
	@echo ""
	@echo "  Pipeline (local):"
	@echo "    make download       - Download data from Binance"
	@echo "    make merge          - Merge data sources"
	@echo "    make features       - Generate features"
	@echo "    make labels         - Generate labels"
	@echo "    make train          - Train models"
	@echo "    make predict        - Run predictions"
	@echo "    make signals        - Generate signals"
	@echo "    make pipeline       - Run full pipeline"
	@echo ""
	@echo "  Utilities:"
	@echo "    make validate       - Validate all configs"
	@echo "    make clean          - Clean generated files"
	@echo "    make test           - Run tests"
	@echo ""

# =============================================================================
# Configuration
# =============================================================================

CONFIG ?= configs/btcusdt_1m_dev.jsonc
SYMBOL ?= BTCUSDT
ENV ?= dev

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
	@echo "📦 Installing Python dependencies..."
	pip install -r requirements.txt
	@echo "✅ Setup complete!"

setup-azure:
	@echo "☁️  Setting up Azure infrastructure..."
	cd $(TF_AZURE_PATH) && terraform init
	cd $(TF_AZURE_PATH) && terraform plan
	@echo "Run 'cd $(TF_AZURE_PATH) && terraform apply' to apply changes"

setup-gcp:
	@echo "☁️  Setting up GCP infrastructure..."
	cd $(TF_GCP_PATH) && terraform init
	cd $(TF_GCP_PATH) && terraform plan
	@echo "Run 'cd $(TF_GCP_PATH) && terraform apply' to apply changes"

# =============================================================================
# Docker
# =============================================================================

docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t $(ACR_SERVER)/$(ACR_REPO):$(IMAGE_TAG) .
	docker tag $(ACR_SERVER)/$(ACR_REPO):$(IMAGE_TAG) $(ACR_SERVER)/$(ACR_REPO):latest

docker-push: docker-build
	@echo "📤 Pushing to Azure Container Registry..."
	docker push $(ACR_SERVER)/$(ACR_REPO):$(IMAGE_TAG)
	docker push $(ACR_SERVER)/$(ACR_REPO):latest

# =============================================================================
# Pipeline - Local Execution
# =============================================================================

download:
	@echo "📥 Downloading data for $(SYMBOL)..."
	python -m scripts.download_binance -c $(CONFIG)

merge:
	@echo "🔗 Merging data..."
	python -m scripts.merge_new -c $(CONFIG)

features:
	@echo "⚙️  Generating features..."
	python -m scripts.features_new -c $(CONFIG)

labels:
	@echo "🏷️  Generating labels..."
	python -m scripts.labels_new -c $(CONFIG)

train:
	@echo "🧠 Training models..."
	python -m scripts.train -c $(CONFIG)

predict:
	@echo "🔮 Running predictions..."
	python -m scripts.predict -c $(CONFIG)

signals:
	@echo "📊 Generating signals..."
	python -m scripts.signals -c $(CONFIG)

pipeline: merge features labels train predict signals
	@echo "✅ Full pipeline complete!"

# =============================================================================
# Utilities
# =============================================================================

validate-configs:
	@echo "🔍 Validating configs..."
	@for f in configs/*.jsonc; do \
		python3 -c "import json, re; content=open('$$f').read(); content=re.sub(r'//.*', '', content); json.loads(content)" 2>&1 \
		&& echo "  ✅ $$f" || echo "  ❌ $$f"; \
	done

clean:
	@echo "🧹 Cleaning generated files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name ".DS_Store" -delete
	@echo "✅ Clean complete!"

test:
	@echo "🧪 Running tests..."
	python -m pytest tests/ -v || echo "No tests found"

# =============================================================================
# Multi-symbol operations
# =============================================================================

download-all:
	@echo "📥 Downloading all symbols..."
	@for symbol in BTCUSDT ETHUSDT BNBUSDT SOLUSDT XRPUSDT; do \
		echo "  Downloading $$symbol..."; \
		python -m scripts.download_binance -c configs/$${symbol,,}_1m_dev.jsonc || true; \
	done

pipeline-all:
	@echo "🚀 Running pipeline for all symbols..."
	@for symbol in BTCUSDT ETHUSDT BNBUSDT SOLUSDT XRPUSDT; do \
		echo "═══════════════════════════════════════════════"; \
		echo "  Processing $$symbol..."; \
		echo "═══════════════════════════════════════════════"; \
		$(MAKE) pipeline CONFIG=configs/$${symbol,,}_1m_dev.jsonc || true; \
	done
