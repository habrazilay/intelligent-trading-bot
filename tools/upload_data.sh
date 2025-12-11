#!/usr/bin/env bash
set -euo pipefail

# ==============================
# Upload data to Azure File Share
# ==============================
#
# Uso:
#   ./tools/upload_data.sh <SYMBOL> <FREQ>
#
# Exemplos:
#   ./tools/upload_data.sh BTCUSDT 1m
#   ./tools/upload_data.sh BTCUSDT 5m
#   ./tools/upload_data.sh BTCUSDT 1h
#   ./tools/upload_data.sh ETHUSDT 5m
#
# Estrutura no Azure:
#   data-itb-{freq}/
#     {SYMBOL}/
#       klines.parquet
#       data.csv
#       features_conservative.csv
#       ...
#
# ==============================

# Parâmetros obrigatórios
SYMBOL="${1:-}"
FREQ="${2:-}"

if [[ -z "$SYMBOL" || -z "$FREQ" ]]; then
  echo "ERRO: Parâmetros obrigatórios não fornecidos."
  echo ""
  echo "Uso: $0 <SYMBOL> <FREQ>"
  echo ""
  echo "Exemplos:"
  echo "  $0 BTCUSDT 1m"
  echo "  $0 BTCUSDT 5m"
  echo "  $0 BTCUSDT 1h"
  exit 1
fi

ACCOUNT="${AZURE_STORAGE_ACCOUNT:-stitbdev}"
SHARE="data-itb-${FREQ}"

LOCAL_DIR="DATA_ITB_${FREQ}/${SYMBOL}"
REMOTE_DIR="$SYMBOL"

echo "==> Upload ${SYMBOL} ${FREQ}"
echo "    Storage account : $ACCOUNT"
echo "    File share      : $SHARE"
echo "    Local dir       : $LOCAL_DIR"
echo "    Remote dir      : $REMOTE_DIR"
echo

if [[ ! -d "$LOCAL_DIR" ]]; then
  echo "ERRO: diretório $LOCAL_DIR não existe."
  exit 1
fi

if [[ -z "${AZURE_STORAGE_ACCOUNT:-}" || -z "${AZURE_STORAGE_KEY:-}" ]]; then
  echo "ERRO: AZURE_STORAGE_ACCOUNT e/ou AZURE_STORAGE_KEY não definidos."
  echo "      export AZURE_STORAGE_ACCOUNT=stitbdev"
  echo "      export AZURE_STORAGE_KEY='...'"
  exit 1
fi

echo "-> Enviando conteúdo de $LOCAL_DIR para $SHARE/$REMOTE_DIR ..."
az storage file upload-batch \
  --account-name "$ACCOUNT" \
  --destination "$SHARE" \
  --destination-path "$REMOTE_DIR" \
  --source "$LOCAL_DIR"

echo "OK: Upload ${SYMBOL} ${FREQ} concluído."
