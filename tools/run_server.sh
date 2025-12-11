#!/bin/bash
###############################################################################
# Server Runner com captura de stderr
#
# Redireciona tanto stdout quanto stderr para o arquivo de log
#
# Uso:
#   ./run_server.sh configs/btcusdt_1m_staging_v2.jsonc
###############################################################################

CONFIG_FILE="${1:-configs/btcusdt_1m_staging_v2.jsonc}"
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/server.log"

# Criar diretório de logs
mkdir -p "$LOG_DIR"

echo "=============================================="
echo "Starting Trading Server"
echo "=============================================="
echo "Config: $CONFIG_FILE"
echo "Log: $LOG_FILE"
echo "=============================================="
echo ""

# Executar servidor com saída completa (stdout + stderr) no log E no terminal
python -u -m service.server -c "$CONFIG_FILE" 2>&1 | tee -a "$LOG_FILE"
