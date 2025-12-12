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
        verify-orderbook collect-orderbook \
        azure-ml-info azure-ml-train azure-ml-list-experiments azure-ml-list-jobs

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
	@echo "    make infra-dev-init   - Terraform init (first time)"
	@echo "    make infra-dev-plan   - Terraform plan (preview changes)"
	@echo "    make infra-dev-apply  - Terraform apply (uses .env.dev secrets)"
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
	@echo "    make analyze SYMBOL=BTCUSDT FREQ=5m  - Analyze data and get recommendations"
	@echo "    make analyze-1m                      - Legacy: analyze_btcusdt_1m.py"
	@echo ""
	@echo "  Upload to Azure:"
	@echo "    make upload-all       - Upload ALL data from DATA_ITB_*"
	@echo "    make upload-list      - List available data for upload"
	@echo "    make upload SYMBOL=BTCUSDT FREQ=5m  - Upload specific"
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
	@echo "    make collect-orderbook-all  - Start ALL symbols (BTC,ETH,BNB,SOL,XRP)"
	@echo "    make collect-orderbook-status - Check collector status"
	@echo "    make collect-orderbook-stop - Stop all collectors"
	@echo "    make verify-orderbook       - Verify collected data"
	@echo ""
	@echo "  GCP Cloud ML:"
	@echo "    make gcp-setup-automated    - Automated GCP setup (15 min)"
	@echo "    make gcp-upload-bigquery    - Upload data to BigQuery (CONFIG=...)"
	@echo "    make gcp-automl             - Run AutoML training (CONFIG=..., BUDGET=1)"
	@echo "    make gcp-lstm               - Run LSTM GPU training (CONFIG=...)"
	@echo "    make gcp-monitor            - Monitor GCP costs"
	@echo ""
	@echo "  Azure ML:"
	@echo "    make azure-ml-info          - Show Azure ML workspace info"
	@echo "    make azure-ml-train         - Submit training job to Azure ML"
	@echo "    make azure-ml-list-jobs     - List recent Azure ML jobs"
	@echo "    make azure-ml-list-experiments - List Azure ML experiments"
	@echo ""
	@echo "  MLflow Tracking (Local → Azure ML):"
	@echo "    make mlflow-train           - Train locally, log to Azure ML (FREE)"
	@echo "    make mlflow-train SYMBOL=ETHUSDT FREQ=5m"
	@echo "    make mlflow-list            - List experiments from Azure ML"
	@echo ""
	@echo "  Quick Commands (Easy!):"
	@echo "    make dl SYMBOL=ETHUSDT FREQ=5m        - Download data"
	@echo "    make run SYMBOL=ETHUSDT FREQ=5m       - Run full pipeline (conservative)"
	@echo "    make run SYMBOL=SOL FREQ=5m STRATEGY=aggressive  - Run with strategy"
	@echo ""
	@echo "  Trade Monitoring (Testnet):"
	@echo "    make monitor          - Start live monitoring (updates every 60s)"
	@echo "    make monitor-once     - Take single snapshot"
	@echo "    make analyze-trades   - Generate full analysis report"
	@echo "    make trade-metrics    - Show trade metrics"
	@echo "    make trade-insights   - Show trading insights"
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

# Azure ML
AZURE_RESOURCE_GROUP ?= rg-itb-dev
AZURE_ML_WORKSPACE ?= mlw-itb-dev
AZURE_ML_COMPUTE ?= itb-training

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

infra-dev-init:
	@echo ">> terraform init em infra/azure/terraform/envs/dev"
	cd infra/azure/terraform/envs/dev && terraform init

infra-dev-plan:
	@echo ">> terraform plan em infra/azure/terraform/envs/dev"
	@echo ">> Carregando secrets do .env.dev..."
	@. .env.dev && \
	 export TF_VAR_binance_api_key=$$BINANCE_API_KEY && \
	 export TF_VAR_binance_api_secret=$$BINANCE_API_SECRET && \
	 cd infra/azure/terraform/envs/dev && terraform plan

infra-dev-apply:
	@echo ">> terraform apply em infra/azure/terraform/envs/dev"
	@echo ">> Carregando secrets do .env.dev..."
	@. .env.dev && \
	 export TF_VAR_binance_api_key=$$BINANCE_API_KEY && \
	 export TF_VAR_binance_api_secret=$$BINANCE_API_SECRET && \
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
		echo "Available Strategies: conservative (default), aggressive, staging, quick"; \
		echo ""; \
		exit 1; \
	fi
	@# Determine config based on STRATEGY
	@if [ "$(STRATEGY)" = "aggressive" ]; then \
		CONFIG=configs/base_aggressive.jsonc; \
	elif [ "$(STRATEGY)" = "staging" ]; then \
		CONFIG=configs/base_staging.jsonc; \
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

# Generic analyze (New!)
analyze:
	@if [ -z "$(SYMBOL)" ] || [ -z "$(FREQ)" ]; then \
		echo ""; \
		echo "ERROR: SYMBOL and FREQ are required!"; \
		echo ""; \
		echo "Usage: make analyze SYMBOL=<symbol> FREQ=<freq> [DAYS=<days>]"; \
		echo ""; \
		echo "Examples:"; \
		echo "  make analyze SYMBOL=BTCUSDT FREQ=5m"; \
		echo "  make analyze SYMBOL=ETHUSDT FREQ=1m DAYS=30"; \
		echo ""; \
		exit 1; \
	fi
	@DAYS=$${DAYS:-90}; \
	echo ">> Analyzing $(SYMBOL) $(FREQ) data (last $$DAYS days)..."; \
	python -m scripts.analyze_data \
	  --symbol $(SYMBOL) \
	  --freq $(FREQ) \
	  --days $$DAYS

# Legacy analyze
analyze-1m:
	@echo ">> analyze_btcusdt_1m.py (local)"
	python my_tests/analyze_btcusdt_1m.py \
	  --parquet DATA_ITB_1m/BTCUSDT/klines.parquet \
	  --days 90

# =============================================================================
# Upload to Azure Files
# =============================================================================

upload-all:
	@echo ">> upload ALL data to Azure Files"
	./tools/upload_data.sh

upload-list:
	@echo ">> list available data for upload"
	./tools/upload_data.sh --list

upload:
	@echo ">> upload $(SYMBOL) $(FREQ) to Azure Files"
	./tools/upload_data.sh $(SYMBOL) $(FREQ)

# Legacy targets (use upload-all instead)
upload-1m:
	@echo ">> upload BTCUSDT 1m para Azure Files"
	./tools/upload_data.sh BTCUSDT 1m

upload-5m:
	@echo ">> upload BTCUSDT 5m para Azure Files"
	./tools/upload_data.sh BTCUSDT 5m

upload-1h:
	@echo ">> upload BTCUSDT 1h para Azure Files"
	./tools/upload_data.sh BTCUSDT 1h

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

# Download missing data (DOGE 5m, DOGE 1m, SOL 1m) in background with nohup
download-missing:
	@echo "Starting downloads for missing data in background..."
	@mkdir -p logs
	nohup python -m scripts.download_binance -c configs/dogeusdt_5m_dev.jsonc > logs/download_dogeusdt_5m.log 2>&1 &
	@echo "DOGE 5m started - log: logs/download_dogeusdt_5m.log"
	nohup python -m scripts.download_binance -c configs/dogeusdt_1m_dev.jsonc > logs/download_dogeusdt_1m.log 2>&1 &
	@echo "DOGE 1m started - log: logs/download_dogeusdt_1m.log"
	nohup python -m scripts.download_binance -c configs/solusdt_1m_dev.jsonc > logs/download_solusdt_1m.log 2>&1 &
	@echo "SOL 1m started - log: logs/download_solusdt_1m.log"
	@echo ""
	@echo "All downloads running in background!"
	@echo "Monitor with: tail -f logs/download_*.log"
	@echo "Check status: ps aux | grep download_binance"

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
	@echo "Starting 7-day orderbook collection for BTCUSDT..."
	@mkdir -p logs
	nohup python scripts/collect_orderbook.py \
		--symbol BTCUSDT \
		--duration 7d \
		--save-interval 30m \
		> logs/orderbook_BTCUSDT.log 2>&1 &
	@echo "BTCUSDT started! PID: $$!"

collect-orderbook-all:
	@echo "Starting 7-day orderbook collection for ALL symbols..."
	@mkdir -p logs
	@for symbol in BTCUSDT ETHUSDT BNBUSDT SOLUSDT XRPUSDT; do \
		echo "Starting $$symbol..."; \
		nohup python scripts/collect_orderbook.py \
			--symbol $$symbol \
			--duration 7d \
			--save-interval 30m \
			> logs/orderbook_$$symbol.log 2>&1 & \
		sleep 2; \
	done
	@echo ""
	@echo "All collectors started!"
	@echo "Monitor: tail -f logs/orderbook_*.log"
	@echo "Status:  ps aux | grep collect_orderbook"
	@echo "Stop:    pkill -f collect_orderbook"

collect-orderbook-status:
	@echo "Orderbook collectors status:"
	@ps aux | grep "[c]ollect_orderbook" || echo "  No collectors running"
	@echo ""
	@echo "Recent logs:"
	@for f in logs/orderbook_*.log; do \
		if [ -f "$$f" ]; then \
			echo "  $$(basename $$f): $$(tail -1 $$f 2>/dev/null || echo 'empty')"; \
		fi; \
	done

collect-orderbook-stop:
	@echo "Stopping all orderbook collectors..."
	@pkill -f "collect_orderbook" || echo "No collectors running"
	@echo "Done"

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

# =============================================================================
# Azure ML Operations
# =============================================================================

azure-ml-info:
	@echo "════════════════════════════════════════════════════════════════"
	@echo "  Azure ML Workspace Info"
	@echo "════════════════════════════════════════════════════════════════"
	@az ml workspace show \
		--name $(AZURE_ML_WORKSPACE) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--output table 2>/dev/null || echo "Workspace not found. Run 'make infra-dev-apply' first."

azure-ml-list-experiments:
	@echo "Listing Azure ML experiments..."
	@az ml experiment list \
		--workspace-name $(AZURE_ML_WORKSPACE) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--output table

azure-ml-list-jobs:
	@echo "Listing recent Azure ML jobs..."
	@az ml job list \
		--workspace-name $(AZURE_ML_WORKSPACE) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--max-results 10 \
		--output table

# =============================================================================
# Trade Monitoring & Analysis (Futures Testnet)
# =============================================================================

monitor:
	@echo "Starting trade monitor (testnet)..."
	python -m scripts.trade_monitor --interval 60

monitor-once:
	@echo "Taking single snapshot..."
	python -m scripts.trade_monitor --once

analyze-trades:
	@echo "Analyzing trade history..."
	python -m scripts.trade_analyzer --report

trade-metrics:
	@echo "Trade metrics:"
	python -m scripts.trade_analyzer --metrics

trade-insights:
	@echo "Trade insights:"
	python -m scripts.trade_analyzer --insights

optimize-thresholds:
	@echo "Analyzing and recommending threshold optimizations..."
	python -m scripts.threshold_optimizer --config base_conservative.jsonc

optimize-apply:
	@echo "Optimizing and applying new thresholds..."
	python -m scripts.threshold_optimizer --config base_conservative.jsonc --apply

optimize-continuous:
	@echo "Starting continuous threshold optimization (every 30min)..."
	python -m scripts.threshold_optimizer --config base_conservative.jsonc --apply --continuous --interval 30

# =============================================================================
# MLflow Tracking (Local training → Azure ML)
# =============================================================================

mlflow-train:
	@echo "Training locally with MLflow tracking to Azure ML..."
	@. .env.dev && python tools/train_with_mlflow.py \
		--symbol $(or $(SYMBOL),BTCUSDT) \
		--freq $(or $(FREQ),5m) \
		--strategy $(or $(STRATEGY),conservative)

mlflow-list:
	@echo "Listing MLflow experiments from Azure ML..."
	@. .env.dev && python tools/train_with_mlflow.py --list --strategy $(or $(STRATEGY),conservative)

# =============================================================================
# Azure ML Training
# =============================================================================

azure-ml-train:
	@if [ -z "$(SYMBOL)" ] || [ -z "$(FREQ)" ]; then \
		echo "╔════════════════════════════════════════════════════════════════╗"; \
		echo "║  Azure ML Training                                              ║"; \
		echo "╚════════════════════════════════════════════════════════════════╝"; \
		echo ""; \
		echo "Usage: make azure-ml-train SYMBOL=<symbol> FREQ=<freq> [STRATEGY=<strategy>]"; \
		echo ""; \
		echo "Examples:"; \
		echo "  make azure-ml-train SYMBOL=BTCUSDT FREQ=5m"; \
		echo "  make azure-ml-train SYMBOL=ETHUSDT FREQ=1h STRATEGY=aggressive"; \
		echo ""; \
		echo "Available Symbols: BTCUSDT, ETHUSDT, BNBUSDT, XRPUSDT"; \
		echo "Available Frequencies: 1m, 5m, 1h"; \
		echo "Available Strategies: conservative (default), aggressive, quick_profit"; \
		echo ""; \
		exit 1; \
	fi
	@STRATEGY_VAL=$${STRATEGY:-conservative}; \
	echo "Submitting Azure ML training job..."; \
	echo "  Symbol:   $(SYMBOL)"; \
	echo "  Freq:     $(FREQ)"; \
	echo "  Strategy: $$STRATEGY_VAL"; \
	echo "  Compute:  $(AZURE_ML_COMPUTE)"; \
	gh workflow run train-azure-ml.yml \
		-f symbol=$(SYMBOL) \
		-f freq=$(FREQ) \
		-f strategy=$$STRATEGY_VAL \
		-f compute_cluster=$(AZURE_ML_COMPUTE); \
	echo ""; \
	echo "Job submitted! Monitor at:"; \
	echo "  GitHub Actions: https://github.com/$$(gh repo view --json owner,name -q '.owner.login + \"/\" + .name')/actions"; \
	echo "  Azure ML Studio: https://ml.azure.com"

# =============================================================================
# Forex Trading (MetaApi + MT5)
# =============================================================================

forex-test:
	@echo "Testing MetaApi MT5 connection..."
	python3 service/adapters/metaapi_adapter.py

forex-download-eurusd:
	@echo "Downloading EURUSD 1h data (Yahoo Finance - FREE)..."
	python -m scripts.download_forex_yfinance --symbol EURUSD --timeframe 1h --days 730

forex-download-all:
	@echo "Downloading all major Forex pairs (Yahoo Finance - FREE)..."
	python -m scripts.download_forex_yfinance --all-pairs --timeframe 1h --days 730

forex-download-metaapi:
	@echo "Downloading EURUSD via MetaApi (requires deployed account)..."
	python -m scripts.download_forex --symbol EURUSD --timeframe 1h --days 365

forex-pipeline-eurusd:
	@echo "Running Forex EURUSD pipeline..."
	python -m scripts.merge -c configs/forex_eurusd_1h.jsonc
	python -m scripts.features -c configs/forex_eurusd_1h.jsonc
	python -m scripts.labels -c configs/forex_eurusd_1h.jsonc
	python -m scripts.train -c configs/forex_eurusd_1h.jsonc
	python -m scripts.predict -c configs/forex_eurusd_1h.jsonc
	python -m scripts.signals -c configs/forex_eurusd_1h.jsonc

forex-shadow:
	@echo "Running Forex EURUSD shadow mode (MT5 Demo)..."
	@echo "Account: MetaQuotes Demo ($100,000)"
	ENABLE_LIVE_TRADING=true python -m service.server -c configs/forex_eurusd_1h_shadow.jsonc

forex-train-full:
	@echo "Full Forex training pipeline..."
	@echo ""
	@echo "Step 1: Download EURUSD data (730 days from Yahoo Finance)..."
	python -m scripts.download_forex_yfinance --symbol EURUSD --timeframe 1h --days 730
	@echo ""
	@echo "Step 2: Run ML pipeline..."
	python -m scripts.merge -c configs/forex_eurusd_1h.jsonc
	python -m scripts.features -c configs/forex_eurusd_1h.jsonc
	python -m scripts.labels -c configs/forex_eurusd_1h.jsonc
	python -m scripts.train -c configs/forex_eurusd_1h.jsonc
	python -m scripts.predict -c configs/forex_eurusd_1h.jsonc
	python -m scripts.signals -c configs/forex_eurusd_1h.jsonc
	@echo ""
	@echo "Training complete! Run 'make forex-shadow' to start shadow mode"

forex-status:
	@echo "MT5 Demo Account Status:"
	@python3 -c "\
from dotenv import load_dotenv; load_dotenv('.env.dev'); \
from service.adapters.metaapi_adapter import MetaApiAdapter; \
adapter = MetaApiAdapter(); \
info = adapter.get_account_info(); \
positions = adapter.get_positions(); \
print(f'  Balance:  \$${info.get(\"balance\", 0):,.2f}'); \
print(f'  Equity:   \$${info.get(\"equity\", 0):,.2f}'); \
print(f'  Margin:   \$${info.get(\"margin\", 0):,.2f}'); \
print(f'  Free:     \$${info.get(\"freeMargin\", 0):,.2f}'); \
print(f'  Positions: {len(positions)}'); \
[print(f'    {p[\"symbol\"]}: {p[\"type\"]} {p[\"volume\"]} @ {p[\"openPrice\"]} | P/L: \$${p.get(\"profit\", 0):.2f}') for p in positions]"

# =============================================================================
# Azure Storage Sync
# =============================================================================

azure-sync:
	@echo "Syncing all data to Azure Storage..."
	python3 -m scripts.sync_to_azure --all

azure-sync-orderbook:
	@echo "Syncing orderbook data to Azure Storage..."
	python3 -m scripts.sync_to_azure --orderbook

azure-sync-trades:
	@echo "Syncing trade logs to Azure Storage..."
	python3 -m scripts.sync_to_azure --trades

azure-sync-data:
	@echo "Syncing klines data to Azure Storage..."
	python3 -m scripts.sync_to_azure --data

azure-sync-dry:
	@echo "Dry run - showing what would be synced..."
	python3 -m scripts.sync_to_azure --all --dry-run

azure-stats:
	@echo "Azure Storage stats..."
	python3 -m scripts.sync_to_azure --stats

# =============================================================================
# Bot Status
# =============================================================================

bot-status:
	@echo "Checking Binance Futures Testnet status..."
	@python3 -c "\
from dotenv import load_dotenv; load_dotenv('.env.dev'); \
import os, time, hmac, hashlib, requests; \
api_key = os.getenv('BINANCE_API_KEY_DEMO'); \
api_secret = os.getenv('BINANCE_API_SECRET_DEMO'); \
base_url = 'https://testnet.binancefuture.com'; \
params = {'timestamp': int(time.time() * 1000)}; \
query = '&'.join(f'{k}={v}' for k, v in params.items()); \
sig = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest(); \
r = requests.get(f'{base_url}/fapi/v2/account?{query}&signature={sig}', headers={'X-MBX-APIKEY': api_key}); \
a = r.json(); \
print('=== BINANCE FUTURES TESTNET ==='); \
print(f'Balance: \$${float(a.get(\"totalWalletBalance\", 0)):,.2f}'); \
print(f'Unrealized PnL: \$${float(a.get(\"totalUnrealizedProfit\", 0)):,.2f}'); \
positions = [p for p in a.get('positions', []) if float(p.get('positionAmt', 0)) != 0]; \
print(f'Open Positions: {len(positions)}'); \
[print(f\"  {p['symbol']}: {'LONG' if float(p['positionAmt']) > 0 else 'SHORT'} {abs(float(p['positionAmt']))} | PnL: \$${float(p['unrealizedProfit']):.2f}\") for p in positions]"

