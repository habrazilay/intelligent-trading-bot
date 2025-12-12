#!/usr/bin/env bash
set -euo pipefail

# ==============================
# Upload data to Azure File Share
# ==============================
#
# Uso:
#   ./tools/upload_data.sh              # Upload ALL data from DATA_ITB_*
#   ./tools/upload_data.sh BTCUSDT      # Upload specific symbol (all freqs)
#   ./tools/upload_data.sh BTCUSDT 5m   # Upload specific symbol + freq
#
# Estrutura local:
#   DATA_ITB_1m/BTCUSDT/...
#   DATA_ITB_5m/BTCUSDT/...
#   DATA_ITB_1h/BTCUSDT/...
#
# Estrutura no Azure:
#   data-itb-1m/BTCUSDT/...
#   data-itb-5m/BTCUSDT/...
#   data-itb-1h/BTCUSDT/...
#
# ==============================

SYMBOL="${1:-}"
FREQ="${2:-}"

ACCOUNT="${AZURE_STORAGE_ACCOUNT:-stitbdev}"

# Verificar credenciais Azure
check_azure_credentials() {
  # Load from .env.dev if exists
  if [[ -f ".env.dev" && -z "${AZURE_STORAGE_KEY:-}" ]]; then
    echo "==> Carregando AZURE_STORAGE_KEY de .env.dev..."
    export AZURE_STORAGE_KEY=$(grep -E "^AZURE_STORAGE_KEY=" .env.dev | cut -d'=' -f2- | tr -d '"' | tr -d "'")
  fi

  if [[ -z "${AZURE_STORAGE_KEY:-}" ]]; then
    echo "==> Buscando storage key via az CLI..."
    export AZURE_STORAGE_KEY=$(az storage account keys list \
      --account-name "$ACCOUNT" \
      --query '[0].value' -o tsv 2>/dev/null || true)

    if [[ -z "${AZURE_STORAGE_KEY:-}" ]]; then
      echo "ERRO: Não foi possível obter AZURE_STORAGE_KEY."
      echo "      Opções:"
      echo "        1. Adicionar AZURE_STORAGE_KEY no .env.dev"
      echo "        2. export AZURE_STORAGE_KEY='...'"
      echo "        3. az login (para usar az CLI)"
      exit 1
    fi
  fi
  export AZURE_STORAGE_ACCOUNT="$ACCOUNT"
  echo "==> Storage key carregada (ending in ...${AZURE_STORAGE_KEY: -4})"
}

# Upload de um diretório específico
upload_dir() {
  local local_dir="$1"
  local freq="$2"
  local symbol="$3"

  local share="data-itb-${freq}"
  local remote_dir="$symbol"

  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "📤 ${symbol} ${freq}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "   Local:  $local_dir"
  echo "   Remote: $share/$remote_dir"

  if [[ ! -d "$local_dir" ]]; then
    echo "   ⚠️  Diretório não existe, pulando..."
    return 0
  fi

  # Contar arquivos
  local file_count=$(find "$local_dir" -type f | wc -l | tr -d ' ')
  echo "   Files: $file_count"

  if [[ "$file_count" -eq 0 ]]; then
    echo "   ⚠️  Nenhum arquivo, pulando..."
    return 0
  fi

  # Upload
  az storage file upload-batch \
    --account-name "$ACCOUNT" \
    --destination "$share" \
    --destination-path "$remote_dir" \
    --source "$local_dir" \
    --only-show-errors

  echo "   ✅ OK"
}

# Main
main() {
  echo "════════════════════════════════════════════════════"
  echo "  Azure File Share Upload"
  echo "════════════════════════════════════════════════════"
  echo "  Account: $ACCOUNT"
  echo ""

  check_azure_credentials

  local uploaded=0
  local skipped=0

  # Detectar diretórios DATA_ITB_*
  for data_dir in DATA_ITB_*/; do
    [[ -d "$data_dir" ]] || continue

    # Extrair freq do nome do diretório (DATA_ITB_5m -> 5m)
    local dir_freq=$(basename "$data_dir" | sed 's/DATA_ITB_//')

    # Filtrar por freq se especificado
    if [[ -n "$FREQ" && "$dir_freq" != "$FREQ" ]]; then
      continue
    fi

    # Iterar sobre symbols dentro do diretório
    for symbol_dir in "${data_dir}"*/; do
      [[ -d "$symbol_dir" ]] || continue

      local dir_symbol=$(basename "$symbol_dir")

      # Filtrar por symbol se especificado
      if [[ -n "$SYMBOL" && "$dir_symbol" != "$SYMBOL" ]]; then
        continue
      fi

      upload_dir "$symbol_dir" "$dir_freq" "$dir_symbol"
      ((uploaded++)) || true
    done
  done

  echo ""
  echo "════════════════════════════════════════════════════"
  echo "  Resumo: $uploaded uploads realizados"
  echo "════════════════════════════════════════════════════"
}

# Mostrar ajuda
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Upload data to Azure File Share"
  echo ""
  echo "Uso:"
  echo "  $0                    Upload ALL data from DATA_ITB_*"
  echo "  $0 BTCUSDT            Upload BTCUSDT (all timeframes)"
  echo "  $0 BTCUSDT 5m         Upload BTCUSDT 5m only"
  echo "  $0 --list             List available data"
  echo ""
  echo "Requer:"
  echo "  - az login (ou AZURE_STORAGE_KEY exportado)"
  echo ""
  exit 0
fi

# Listar dados disponíveis
if [[ "${1:-}" == "--list" ]]; then
  echo "Dados disponíveis:"
  echo ""
  for data_dir in DATA_ITB_*/; do
    [[ -d "$data_dir" ]] || continue
    freq=$(basename "$data_dir" | sed 's/DATA_ITB_//')
    echo "  $freq:"
    for symbol_dir in "${data_dir}"*/; do
      [[ -d "$symbol_dir" ]] || continue
      symbol=$(basename "$symbol_dir")
      files=$(find "$symbol_dir" -type f | wc -l | tr -d ' ')
      echo "    - $symbol ($files files)"
    done
    echo ""
  done
  exit 0
fi

main
