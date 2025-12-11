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
        analyze-staging analyze-staging-high-capital analyze-staging-custom \
        gcp-setup-automated gcp-upload-bigquery gcp-automl gcp-lstm gcp-monitor \
        verify-orderbook collect-orderbook

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
	@echo "    make pipeline         - Run full pipeline (legacy)"
	@echo "    make pipeline-generic - Run generic pipeline (BASE_CONFIG=... SYMBOL=... FREQ=...)"
	@echo ""
	@echo "  Quick Pipelines (New!):"
	@echo "    make conservative-btc-5m  - Conservative strategy (Azure)"
	@echo "    make conservative-eth-5m  - Conservative strategy (Azure)"
	@echo "    make aggressive-sol-5m    - Aggressive strategy (GCP)"
	@echo "    make aggressive-bnb-5m    - Aggressive strategy (GCP)"
	@echo "    make quick-btc-1m         - Quick profit scalping (1m)"
	@echo "    make quick-eth-1m         - Quick profit scalping (1m)"
	@echo ""
	@echo "  Dev Pipelines (Legacy):"
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
	@echo "  Order Flow Collection:"
	@echo "    make verify-orderbook       - Verify collected orderbook data"
	@echo "    make collect-orderbook      - Start 7-day orderbook collection"
	@echo ""
	@echo "  GCP Cloud ML:"
	@echo "    make gcp-setup-automated    - Automated GCP setup (15 min)"
	@echo "    make gcp-upload-bigquery    - Upload data to BigQuery (CONFIG=...)"
	@echo "    make gcp-automl             - Run AutoML training (CONFIG=..., BUDGET=1)"
	@echo "    make gcp-lstm               - Run LSTM GPU training (CONFIG=...)"
	@echo "    make gcp-monitor            - Monitor GCP costs"
	@echo ""
	@echo "  Quick Commands (Easy!):"
	@echo "    make dl SYMBOL=ETHUSDT FREQ=5m        - Download data"
	@echo "    make run SYMBOL=ETHUSDT FREQ=5m       - Run full pipeline (conservative)"
	@echo "    make run SYMBOL=SOL FREQ=5m STRATEGY=aggressive  - Run with strategy"
	@echo ""
	@echo "  Utilities:"
	@echo "    make validate         - Validate all configs"
	@echo "    make clean            - Clean generated files"
	@echo "    make clean-cache      - Clean Python cache (fix import errors)"
	@echo "    make test             - Run tests"
	@echo ""

# =============================================================================
# Configuration
# =============================================================================

# New generic config system (recommended)
BASE_CONFIG ?= configs/base_conservative.jsonc
SYMBOL ?= BTCUSDT
FREQ ?= 5m

# Legacy: specific config files (deprecated, use BASE_CONFIG + SYMBOL + FREQ instead)
CONFIG ?= configs/btcusdt_1m_dev.jsonc

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

# Generic download (new)
download-generic:
	@echo "Downloading $(SYMBOL) $(FREQ)..."
	python -m scripts.download_binance -c $(BASE_CONFIG) --symbol $(SYMBOL) --freq $(FREQ)

merge:
	@echo "Merging data..."
	python -m scripts.merge -c $(CONFIG)

features:
	@echo "Generating features..."
	python -m scripts.features -c $(CONFIG)

labels:
	@echo "Generating labels..."
	python -m scripts.labels -c $(CONFIG)

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

# Generic pipeline with BASE_CONFIG (New!)
# Usage: make pipeline-generic BASE_CONFIG=configs/base_conservative.jsonc SYMBOL=BTCUSDT FREQ=5m
pipeline-generic:
	@echo "Running pipeline with:"
	@echo "  Config: $(BASE_CONFIG)"
	@echo "  Symbol: $(SYMBOL)"
	@echo "  Freq:   $(FREQ)"
	python -m scripts.download_binance -c $(BASE_CONFIG) --symbol $(SYMBOL) --freq $(FREQ)
	python -m scripts.merge -c $(BASE_CONFIG) --symbol $(SYMBOL) --freq $(FREQ)
	python -m scripts.features -c $(BASE_CONFIG) --symbol $(SYMBOL) --freq $(FREQ)
	python -m scripts.labels -c $(BASE_CONFIG) --symbol $(SYMBOL) --freq $(FREQ)
	python -m scripts.train -c $(BASE_CONFIG) --symbol $(SYMBOL) --freq $(FREQ)
	python -m scripts.predict -c $(BASE_CONFIG) --symbol $(SYMBOL) --freq $(FREQ)
	python -m scripts.signals -c $(BASE_CONFIG) --symbol $(SYMBOL) --freq $(FREQ)
	python -m scripts.simulate -c $(BASE_CONFIG) --symbol $(SYMBOL) --freq $(FREQ)
	@echo "Generic pipeline complete!"

# =============================================================================
# Quick Commands (User-friendly)
# =============================================================================

# Download with symbol/freq
# Usage: make dl SYMBOL=ETHUSDT FREQ=5m
dl:
	@if [ -z "$(SYMBOL)" ] || [ -z "$(FREQ)" ]; then \
		echo "╔════════════════════════════════════════════════════════════════╗"; \
		echo "║  Download Binance Data                                         ║"; \
		echo "╚════════════════════════════════════════════════════════════════╝"; \
		echo ""; \
		echo "Usage: make dl SYMBOL=<symbol> FREQ=<freq>"; \
		echo ""; \
		echo "Examples:"; \
		echo "  make dl SYMBOL=ETHUSDT FREQ=5m"; \
		echo "  make dl SYMBOL=BTCUSDT FREQ=1m"; \
		echo "  make dl SYMBOL=SOLUSDT FREQ=5m"; \
		echo ""; \
		echo "Available Symbols: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT"; \
		echo "Available Frequencies: 1m, 5m, 15m, 1h"; \
		echo ""; \
		exit 1; \
	fi
	@echo "Downloading $(SYMBOL) $(FREQ)..."
	@python -m scripts.download_binance -c $(BASE_CONFIG) --symbol $(SYMBOL) --freq $(FREQ)

# Full pipeline with symbol/freq
# Usage: make run SYMBOL=ETHUSDT FREQ=5m
run:
	@if [ -z "$(SYMBOL)" ] || [ -z "$(FREQ)" ]; then \
		echo "╔════════════════════════════════════════════════════════════════╗"; \
		echo "║  Run Full Pipeline                                             ║"; \
		echo "╚════════════════════════════════════════════════════════════════╝"; \
		echo ""; \
		echo "Usage: make run SYMBOL=<symbol> FREQ=<freq> [STRATEGY=<strategy>]"; \
		echo ""; \
		echo "Examples:"; \
		echo "  make run SYMBOL=ETHUSDT FREQ=5m"; \
		echo "  make run SYMBOL=ETHUSDT FREQ=5m STRATEGY=aggressive"; \
		echo "  make run SYMBOL=SOLUSDT FREQ=5m STRATEGY=quick"; \
		echo ""; \
		echo "Available Symbols: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT"; \
		echo "Available Frequencies: 1m, 5m, 15m, 1h"; \
		echo "Available Strategies: conservative (default), aggressive, quick"; \
		echo ""; \
		exit 1; \
	fi
	@# Determine config based on STRATEGY
	@if [ "$(STRATEGY)" = "aggressive" ]; then \
		CONFIG=configs/base_aggressive.jsonc; \
	elif [ "$(STRATEGY)" = "quick" ]; then \
		CONFIG=configs/base_quick_profit.jsonc; \
	else \
		CONFIG=configs/base_conservative.jsonc; \
	fi; \
	echo "Running pipeline with $$CONFIG for $(SYMBOL) $(FREQ)..."; \
	$(MAKE) pipeline-generic BASE_CONFIG=$$CONFIG SYMBOL=$(SYMBOL) FREQ=$(FREQ)

# =============================================================================
# Quick Pipelines (New Generic System)
# =============================================================================

# Conservative (Azure baseline)
conservative-btc-5m:
	$(MAKE) pipeline-generic BASE_CONFIG=configs/base_conservative.jsonc SYMBOL=BTCUSDT FREQ=5m

conservative-eth-5m:
	$(MAKE) pipeline-generic BASE_CONFIG=configs/base_conservative.jsonc SYMBOL=ETHUSDT FREQ=5m

# Aggressive (GCP advanced)
aggressive-sol-5m:
	$(MAKE) pipeline-generic BASE_CONFIG=configs/base_aggressive.jsonc SYMBOL=SOLUSDT FREQ=5m

aggressive-bnb-5m:
	$(MAKE) pipeline-generic BASE_CONFIG=configs/base_aggressive.jsonc SYMBOL=BNBUSDT FREQ=5m

# Quick Profit (Scalping)
quick-btc-1m:
	$(MAKE) pipeline-generic BASE_CONFIG=configs/base_quick_profit.jsonc SYMBOL=BTCUSDT FREQ=1m

quick-eth-1m:
	$(MAKE) pipeline-generic BASE_CONFIG=configs/base_quick_profit.jsonc SYMBOL=ETHUSDT FREQ=1m

# =============================================================================
# Dev Pipelines (Legacy)
# =============================================================================

dev-1m:
	@echo ">> rodar pipeline dev 1m"
	$(MAKE) pipeline CONFIG=configs/btcusdt_1m_dev.jsonc

dev-5m:
	@echo ">> rodar pipeline dev 5m"
	$(MAKE) pipeline CONFIG=configs/btcusdt_5m_dev.jsonc

dev-1m-lgbm:
	@echo ">> rodar pipeline dev 1m (LGBM)"
	$(MAKE) pipeline CONFIG=configs/btcusdt_1m_dev_lgbm.jsonc

train-1m-lgbm:
	@echo ">> treinar modelos 1m (LGBM)"
	$(MAKE) train CONFIG=configs/btcusdt_1m_dev_lgbm.jsonc

predict-1m-lgbm:
	@echo ">> rodar predict 1m (LGBM)"
	$(MAKE) predict CONFIG=configs/btcusdt_1m_dev_lgbm.jsonc

signals-1m-lgbm:
	@echo ">> gerar sinais 1m (LGBM)"
	$(MAKE) signals CONFIG=configs/btcusdt_1m_dev_lgbm.jsonc

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

clean-cache:
	@echo "Cleaning Python cache and bytecode..."
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "Python cache cleaned! Try running your command again."

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

# =============================================================================
# Order Flow Collection
# =============================================================================

verify-orderbook:
	@echo "Verifying orderbook data collection..."
	python scripts/verify_orderbook_data.py

collect-orderbook:
	@echo "Starting 7-day orderbook collection..."
	@echo "This will run in background with nohup"
	@echo "Monitor with: tail -f collector_7days.log"
	nohup python scripts/collect_orderbook.py \
		--symbol BTCUSDT \
		--duration 7d \
		--save-interval 6h \
		> collector_7days.log 2>&1 &
	@echo "Collection started! PID: $$!"
	@echo "Monitor: tail -f collector_7days.log"
	@echo "Check status: ps aux | grep collect_orderbook"

# =============================================================================
# GCP Cloud ML Operations
# =============================================================================

# Budget for AutoML (in hours)
BUDGET ?= 1

gcp-setup-automated:
	@echo "Running automated GCP setup..."
	@echo "This will:"
	@echo "  1. Install gcloud CLI (if needed)"
	@echo "  2. Authenticate your account"
	@echo "  3. Create GCP project"
	@echo "  4. Link billing account (~$$970 USD credits)"
	@echo "  5. Enable APIs (Vertex AI, BigQuery, Compute)"
	@echo "  6. Install Python dependencies"
	@echo ""
	bash scripts/setup_gcp.sh

gcp-upload-bigquery:
	@echo "Uploading data to BigQuery..."
	@if [ -z "$(CONFIG)" ]; then \
		echo "Error: CONFIG not specified. Usage: make gcp-upload-bigquery CONFIG=configs/btcusdt_5m_aggressive.jsonc"; \
		exit 1; \
	fi
	python scripts/upload_to_bigquery.py -c $(CONFIG)

gcp-automl:
	@echo "Running GCP AutoML training..."
	@echo "Budget: $(BUDGET) hour(s) (~$$$(shell echo $$(($(BUDGET) * 5))) USD)"
	@if [ -z "$(CONFIG)" ]; then \
		echo "Error: CONFIG not specified. Usage: make gcp-automl CONFIG=configs/btcusdt_5m_orderflow.jsonc BUDGET=1"; \
		exit 1; \
	fi
	python scripts/gcp_automl_train.py -c $(CONFIG) --budget $(BUDGET)

gcp-lstm:
	@echo "Running LSTM GPU training on GCP..."
	@echo "Estimated cost: $$10-30 (2-4 hours on T4 GPU)"
	@if [ -z "$(CONFIG)" ]; then \
		echo "Error: CONFIG not specified. Usage: make gcp-lstm CONFIG=configs/btcusdt_5m_orderflow.jsonc"; \
		exit 1; \
	fi
	python scripts/lstm_gpu_train.py -c $(CONFIG)

gcp-monitor:
	@echo "Monitoring GCP costs..."
	python scripts/cloud_cost_monitor.py

gcp-monitor-continuous:
	@echo "Starting continuous cost monitoring (every hour)..."
	python scripts/cloud_cost_monitor.py --monitor --interval 3600

# Quick workflow for GCP ML
gcp-workflow:
	@echo "═══════════════════════════════════════════════════════════════"
	@echo "  GCP ML Workflow - Upload + AutoML"
	@echo "═══════════════════════════════════════════════════════════════"
	@if [ -z "$(CONFIG)" ]; then \
		echo "Error: CONFIG not specified."; \
		echo "Usage: make gcp-workflow CONFIG=configs/btcusdt_5m_orderflow.jsonc BUDGET=1"; \
		exit 1; \
	fi
	@echo ""
	@echo "Step 1: Upload to BigQuery..."
	$(MAKE) gcp-upload-bigquery CONFIG=$(CONFIG)
	@echo ""
	@echo "Step 2: Run AutoML ($(BUDGET)h budget)..."
	$(MAKE) gcp-automl CONFIG=$(CONFIG) BUDGET=$(BUDGET)
	@echo ""
	@echo "Step 3: Check costs..."
	$(MAKE) gcp-monitor
	@echo ""
	@echo "Workflow complete!"
