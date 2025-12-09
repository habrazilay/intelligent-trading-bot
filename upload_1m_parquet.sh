#!/usr/bin/env bash
set -euo pipefail

# ==============================
# Config
# ==============================
ACCOUNT="${AZURE_STORAGE_ACCOUNT:-stitbdev}"
SHARE="data-itb-1m"
PAIR="BTCUSDT"

# Versão vem do primeiro argumento ou do env VERSION ou data
VERSION="${1:-${VERSION:-v$(date +%Y-%m-%d)}}"

LOCAL_DIR="DATA_ITB_1m/BTCUSDT"
REMOTE_PREFIX="$PAIR/$VERSION"

echo "==> Upload BTCUSDT 1m"
echo "    Storage account : $ACCOUNT"
echo "    File share      : $SHARE"
echo "    Versão          : $VERSION"
echo "    Local dir       : $LOCAL_DIR"
echo "    Remote prefix   : $REMOTE_PREFIX"
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

# Upload em batch de TUDO que está em DATA_ITB_1m/BTCUSDT
echo "-> Enviando conteúdo de $LOCAL_DIR para $SHARE/$REMOTE_PREFIX ..."
az storage file upload-batch \
  --account-name "$ACCOUNT" \
  --destination "$SHARE" \
  --destination-path "$REMOTE_PREFIX" \
  --source "$LOCAL_DIR"

echo "OK: Upload BTCUSDT 1m concluído."