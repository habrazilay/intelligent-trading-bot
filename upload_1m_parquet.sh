#!/usr/bin/env bash
set -euo pipefail

# ============================
# Config padrão (pode sobrescrever via env)
# ============================
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:-stitbdev}"
SHARE_1M="${SHARE_1M:-data-itb-1m}"

# Versão vem do 1º argumento ou do env VERSION ou data de hoje
VERSION="${1:-${VERSION:-$(date +v%Y-%m-%d)}}"

LOCAL_DIR="DATA_ITB_1m/BTCUSDT"
REMOTE_DIR="BTCUSDT/${VERSION}"

echo "==> Upload BTCUSDT 1m"
echo "    Storage account : ${STORAGE_ACCOUNT}"
echo "    File share      : ${SHARE_1M}"
echo "    Versão          : ${VERSION}"
echo "    Local dir       : ${LOCAL_DIR}"
echo "    Remote dir      : ${REMOTE_DIR}"
echo

# Garantir que o arquivo existe
if [[ ! -f "${LOCAL_DIR}/klines.parquet" ]]; then
  echo "ERRO: ${LOCAL_DIR}/klines.parquet não encontrado."
  exit 1
fi

# Requer: az login + az account set já feitos
echo "-> Enviando klines.parquet ..."
az storage file upload \
  --auth-mode login \
  --enable-file-backup-request-intent true \
  --account-name "${STORAGE_ACCOUNT}" \
  --share-name "${SHARE_1M}" \
  --source "${LOCAL_DIR}/klines.parquet" \
  --path "${REMOTE_DIR}/klines.parquet"

echo "OK: Upload concluído."

# klines.parquet
az storage file upload \
  --share-name data-itb-1m \
  --path BTCUSDT/$VERSION/klines.parquet \
  --source DATA_ITB_1m/BTCUSDT/klines.parquet

# data / features / matrix / predictions / signals / models (se quiser)
az storage file upload \
  --share-name data-itb-1m \
  --path BTCUSDT/$VERSION/data.csv \
  --source DATA_ITB_1m/BTCUSDT/data.csv

az storage file upload \
  --share-name data-itb-1m \
  --path BTCUSDT/$VERSION/features.csv \
  --source DATA_ITB_1m/BTCUSDT/features.csv

az storage file upload \
  --share-name data-itb-1m \
  --path BTCUSDT/$VERSION/matrix.csv \
  --source DATA_ITB_1m/BTCUSDT/matrix.csv

az storage file upload \
  --share-name data-itb-1m \
  --path BTCUSDT/$VERSION/predictions.csv \
  --source DATA_ITB_1m/BTCUSDT/predictions.csv

az storage file upload \
  --share-name data-itb-1m \
  --path BTCUSDT/$VERSION/signals.csv \
  --source DATA_ITB_1m/BTCUSDT/signals.csv