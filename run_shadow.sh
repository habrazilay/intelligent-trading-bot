#!/bin/bash
###############################################################################
# Shadow Mode Runner
#
# Roda múltiplas sessões de shadow trading em paralelo.
# Conecta na Binance real mas simula todas as ordens.
#
# Uso:
#   ./run_shadow.sh                                    # Usa config padrão
#   ./run_shadow.sh configs/btcusdt_1m_staging.jsonc   # Config específico
#   ./run_shadow.sh config1.jsonc config2.jsonc        # Múltiplos em paralelo
#
# Opções:
#   --balance 5000     # Saldo inicial simulado
#   --suffix test_v2   # Sufixo para nomear a sessão
#   --sequential       # Rodar sequencialmente (não paralelo)
###############################################################################

set -e

# Defaults
DEFAULT_CONFIG="configs/btcusdt_1m_staging_v2.jsonc"
BALANCE=1000
SUFFIX=""
PARALLEL="--parallel"
CONFIGS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --balance)
            BALANCE="$2"
            shift 2
            ;;
        --suffix)
            SUFFIX="$2"
            shift 2
            ;;
        --sequential)
            PARALLEL="--sequential"
            shift
            ;;
        --parallel)
            PARALLEL="--parallel"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [config1.jsonc] [config2.jsonc] [--balance N] [--suffix S] [--sequential]"
            echo ""
            echo "Options:"
            echo "  --balance N     Initial simulated balance in USDT (default: 1000)"
            echo "  --suffix S      Strategy suffix for session naming"
            echo "  --sequential    Run configs sequentially instead of parallel"
            echo "  --parallel      Run configs in parallel (default)"
            echo ""
            echo "Examples:"
            echo "  $0                                           # Use default config"
            echo "  $0 configs/btcusdt_1m_aggressive.jsonc       # Single config"
            echo "  $0 config1.jsonc config2.jsonc --parallel    # Multiple parallel"
            exit 0
            ;;
        *)
            # Assume it's a config file
            CONFIGS+=("$1")
            shift
            ;;
    esac
done

# Use default if no configs specified
if [ ${#CONFIGS[@]} -eq 0 ]; then
    CONFIGS=("$DEFAULT_CONFIG")
fi

# Build command
CMD="python run_shadow.py"

for cfg in "${CONFIGS[@]}"; do
    CMD="$CMD -c $cfg"
done

CMD="$CMD --balance $BALANCE $PARALLEL"

if [ -n "$SUFFIX" ]; then
    CMD="$CMD --suffix $SUFFIX"
fi

# Print header
echo "=============================================="
echo "SHADOW MODE TRADING"
echo "=============================================="
echo "Configs: ${CONFIGS[*]}"
echo "Balance: \$$BALANCE"
echo "Mode: ${PARALLEL#--}"
echo "=============================================="
echo ""

# Run
exec $CMD
