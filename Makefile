# ===========================
# Intelligent Trading Bot - Makefile
# ===========================
# Como usar:
#   make infra-dev-apply   # aplica Terraform em dev
#   make image-dev         # build & push imagem dev
#   make dev-1m            # roda pipeline dev 1m (GitHub Actions ou local)
#   make dev-5m            # roda pipeline dev 5m
#   make analyze-1m        # roda analyze_btcusdt_1m.py (local ou ACI)
#   make upload-1m         # sobe DATA_ITB_1m/BTCUSDT pro Azure Files
#   make upload-5m         # idem 5m
#   make upload-1h         # idem 1h

.PHONY: infra-dev-apply image-dev dev-1m dev-5m analyze-1m \
        upload-1m upload-5m upload-1h

# Atualizar infra dev (storage, ACR etc.)
infra-dev-apply:
	@echo ">> terraform apply em infra/azure/terraform/envs/dev"
	cd infra/azure/terraform/envs/dev && terraform apply

# Build & push imagem dev (exemplo – ajuste para seu pipeline real)
image-dev:
	@echo ">> build & push imagem dev para itbacr.azurecr.io/itb-bot"
	# docker build / docker push ou github actions dispatch aqui

# Rodar pipeline dev 1m (exemplo: chamar workflow via gh / script local)
dev-1m:
	@echo ">> rodar pipeline dev 1m (ajuste este alvo conforme seu fluxo)"
	# python -m scripts... ou gh workflow run ...

# Rodar pipeline dev 5m
dev-5m:
	@echo ">> rodar pipeline dev 5m (ajuste este alvo conforme seu fluxo)"
	# idem acima

# Rodar análise 1m (analyze_btcusdt_1m.py) local
analyze-1m:
	@echo ">> analyze_btcusdt_1m.py (local)"
	python my_tests/analyze_btcusdt_1m.py \
	  --parquet DATA_ITB_1m/BTCUSDT/klines.parquet \
	  --days 90

# Upload BTCUSDT 1m para Azure Files
upload-1m:
	@echo ">> upload BTCUSDT 1m para Azure Files"
	./upload_1m_parquet.sh v2025-12-05

# Upload BTCUSDT 5m para Azure Files (script precisa existir)
upload-5m:
	@echo ">> upload BTCUSDT 5m para Azure Files"
	./upload_5m_parquet.sh v2025-12-05

# Upload BTCUSDT 1h para Azure Files (script precisa existir)
upload-1h:
	@echo ">> upload BTCUSDT 1h para Azure Files"
	./upload_1h_parquet.sh v2025-12-05