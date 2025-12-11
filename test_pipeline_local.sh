#!/bin/bash
###############################################################################
# Script de Teste Local - Pipeline Completo
#
# Testa TODOS os scripts do projeto antes de automatizar no CI/CD Azure
#
# Uso:
#   ./test_pipeline_local.sh [--full|--quick|--new-only]
#
# Modos:
#   --full      : Testa pipeline completo (antigo + novo) - demora ~30min
#   --quick     : Teste rápido com dados pequenos - ~5min
#   --new-only  : Testa apenas scripts novos (merge_new, features_new, etc)
#
###############################################################################

set -e  # Para na primeira falha

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
MODE="${1:---quick}"  # Default: quick mode
CONFIG_FILE="configs/btcusdt_1m_dev.jsonc"
TEST_DATA_FOLDER="./DATA_ITB_TEST"
LOG_FILE="test_pipeline_$(date +%Y%m%d_%H%M%S).log"

# Funções auxiliares
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1" | tee -a "$LOG_FILE"
}

section() {
    echo "" | tee -a "$LOG_FILE"
    echo "=================================================================" | tee -a "$LOG_FILE"
    echo "  $1" | tee -a "$LOG_FILE"
    echo "=================================================================" | tee -a "$LOG_FILE"
}

run_test() {
    local test_name="$1"
    local test_cmd="$2"

    log_info "Executando: $test_name"
    log_info "Comando: $test_cmd"

    if eval "$test_cmd" >> "$LOG_FILE" 2>&1; then
        log_success "$test_name - PASSOU"
        return 0
    else
        log_error "$test_name - FALHOU"
        log_error "Veja detalhes em: $LOG_FILE"
        return 1
    fi
}

check_dependencies() {
    section "Verificando Dependências"

    # Python
    if command -v python &> /dev/null; then
        PYTHON_VERSION=$(python --version)
        log_success "Python encontrado: $PYTHON_VERSION"
    else
        log_error "Python não encontrado"
        exit 1
    fi

    # Pacotes Python necessários
    log_info "Verificando pacotes Python..."
    python -c "import pandas, numpy, talib, lightgbm, click, binance" 2>> "$LOG_FILE"
    if [ $? -eq 0 ]; then
        log_success "Todos os pacotes Python necessários estão instalados"
    else
        log_error "Pacotes Python faltando. Execute: pip install -r requirements.txt"
        exit 1
    fi

    # Verifica .env
    if [ -f ".env" ]; then
        log_success "Arquivo .env encontrado"
    else
        log_warning "Arquivo .env não encontrado - algumas funcionalidades podem não funcionar"
        log_warning "Copie .env.sample para .env e configure suas chaves"
    fi
}

cleanup_test_data() {
    log_info "Limpando dados de teste antigos..."
    if [ -d "$TEST_DATA_FOLDER" ]; then
        rm -rf "$TEST_DATA_FOLDER"
        log_success "Dados de teste limpos"
    fi
}

###############################################################################
# TESTES DO PIPELINE ANTIGO (scripts originais do README)
###############################################################################

test_old_pipeline() {
    section "Testando Pipeline ANTIGO (scripts originais)"

    local test_config="$CONFIG_FILE"

    # 1. Download Binance
    log_info "1/8 - Download Binance"
    run_test "download_binance" \
        "python -m scripts.download_binance -c $test_config"

    # 2. Merge
    log_info "2/8 - Merge"
    if [ -f "scripts/merge.py" ]; then
        run_test "merge" \
            "python -m scripts.merge -c $test_config"
    else
        log_warning "scripts/merge.py não encontrado - pulando"
    fi

    # 3. Features
    log_info "3/8 - Features"
    if [ -f "scripts/features.py" ]; then
        run_test "features" \
            "python -m scripts.features -c $test_config"
    else
        log_warning "scripts/features.py não encontrado - pulando"
    fi

    # 4. Labels
    log_info "4/8 - Labels"
    if [ -f "scripts/labels.py" ]; then
        run_test "labels" \
            "python -m scripts.labels -c $test_config"
    else
        log_warning "scripts/labels.py não encontrado - pulando"
    fi

    # 5. Train
    log_info "5/8 - Train"
    run_test "train" \
        "python -m scripts.train -c $test_config"

    # 6. Predict
    log_info "6/8 - Predict"
    if [ -f "scripts/predict.py" ]; then
        run_test "predict" \
            "python -m scripts.predict -c $test_config"
    else
        log_warning "scripts/predict.py não encontrado - pulando"
    fi

    # 7. Signals
    log_info "7/8 - Signals"
    run_test "signals" \
        "python -m scripts.signals -c $test_config"

    # 8. Output
    log_info "8/8 - Output"
    run_test "output" \
        "python -m scripts.output -c $test_config"
}

###############################################################################
# TESTES DOS NOVOS SCRIPTS
###############################################################################

test_new_scripts() {
    section "Testando NOVOS Scripts"

    local test_config="$CONFIG_FILE"

    # 1. collect_orderbook (teste curto - 30 segundos)
    log_info "1/6 - Collect Orderbook (30s)"
    run_test "collect_orderbook" \
        "timeout 35s python scripts/collect_orderbook.py --symbol BTCUSDT --duration 30s --save-interval 15s --output DATA_ORDERBOOK_TEST || true"

    # 2. verify_orderbook_data
    log_info "2/6 - Verify Orderbook Data"
    if [ -d "DATA_ORDERBOOK_TEST" ]; then
        # Temporariamente renomeia para o script encontrar
        mv DATA_ORDERBOOK DATA_ORDERBOOK_BACKUP 2>/dev/null || true
        mv DATA_ORDERBOOK_TEST DATA_ORDERBOOK

        run_test "verify_orderbook_data" \
            "python scripts/verify_orderbook_data.py"

        # Restaura
        mv DATA_ORDERBOOK DATA_ORDERBOOK_TEST
        mv DATA_ORDERBOOK_BACKUP DATA_ORDERBOOK 2>/dev/null || true
    else
        log_warning "DATA_ORDERBOOK_TEST não encontrado - pulando verify_orderbook_data"
    fi

    # 3. merge_new (com --dry-run primeiro)
    log_info "3/6 - Merge New (dry-run)"
    run_test "merge_new_dryrun" \
        "python -m scripts.merge_new -c $test_config --dry-run"

    log_info "3/6 - Merge New (real)"
    run_test "merge_new" \
        "python -m scripts.merge_new -c $test_config"

    # 4. features_new
    log_info "4/6 - Features New (dry-run)"
    run_test "features_new_dryrun" \
        "python -m scripts.features_new -c $test_config --dry-run"

    log_info "4/6 - Features New (real)"
    run_test "features_new" \
        "python -m scripts.features_new -c $test_config"

    # 5. labels_new
    log_info "5/6 - Labels New (dry-run)"
    run_test "labels_new_dryrun" \
        "python -m scripts.labels_new -c $test_config --dry-run"

    log_info "5/6 - Labels New (real)"
    run_test "labels_new" \
        "python -m scripts.labels_new -c $test_config"

    # 6. train (reutiliza o script antigo, mas com dados novos)
    log_info "6/6 - Train (com dados dos scripts novos)"
    run_test "train_new_data" \
        "python -m scripts.train -c $test_config"
}

###############################################################################
# TESTES DE INTEGRAÇÃO
###############################################################################

test_integration() {
    section "Testes de Integração"

    # Verifica se os arquivos de saída foram criados
    log_info "Verificando arquivos de saída..."

    local symbol=$(python -c "import json; print(json.load(open('$CONFIG_FILE'.replace('.jsonc', '.json')))['symbol'])" 2>/dev/null || echo "BTCUSDT")
    local data_folder="DATA_ITB_1m"

    local files_to_check=(
        "$data_folder/$symbol/klines.parquet"
        "$data_folder/$symbol/data.csv"
        "$data_folder/$symbol/features.csv"
        "$data_folder/$symbol/matrix.csv"
    )

    local all_ok=true
    for file in "${files_to_check[@]}"; do
        if [ -f "$file" ]; then
            local size=$(du -h "$file" | cut -f1)
            log_success "Arquivo encontrado: $file ($size)"
        else
            log_warning "Arquivo não encontrado: $file"
            all_ok=false
        fi
    done

    if [ "$all_ok" = true ]; then
        log_success "Todos os arquivos de saída foram criados"
    else
        log_warning "Alguns arquivos de saída estão faltando"
    fi
}

###############################################################################
# RELATÓRIO FINAL
###############################################################################

print_summary() {
    section "Resumo dos Testes"

    echo "" | tee -a "$LOG_FILE"
    log_info "Log completo salvo em: $LOG_FILE"

    # Conta sucessos e falhas no log
    local total_tests=$(grep -c "\[INFO\] Executando:" "$LOG_FILE" || echo "0")
    local passed_tests=$(grep -c "\[✓\].*PASSOU" "$LOG_FILE" || echo "0")
    local failed_tests=$(grep -c "\[✗\].*FALHOU" "$LOG_FILE" || echo "0")

    echo "" | tee -a "$LOG_FILE"
    log_info "Total de testes: $total_tests"
    log_success "Testes passados: $passed_tests"
    if [ "$failed_tests" -gt 0 ]; then
        log_error "Testes falhados: $failed_tests"
    else
        log_success "Testes falhados: 0"
    fi

    echo "" | tee -a "$LOG_FILE"

    if [ "$failed_tests" -eq 0 ]; then
        log_success "========================================="
        log_success "  TODOS OS TESTES PASSARAM! ✓"
        log_success "========================================="
        log_info ""
        log_info "Próximos passos:"
        log_info "1. Revise o log: cat $LOG_FILE"
        log_info "2. Se tudo estiver OK, atualize o CI/CD na Azure"
        log_info "3. Execute: ./scripts/deploy_azure.sh"
        return 0
    else
        log_error "========================================="
        log_error "  ALGUNS TESTES FALHARAM! ✗"
        log_error "========================================="
        log_info ""
        log_info "Ações recomendadas:"
        log_info "1. Revise os erros no log: cat $LOG_FILE"
        log_info "2. Corrija os problemas encontrados"
        log_info "3. Execute novamente: ./test_pipeline_local.sh"
        return 1
    fi
}

###############################################################################
# MAIN
###############################################################################

main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║        TESTE LOCAL - INTELLIGENT TRADING BOT PIPELINE         ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""

    log_info "Modo de teste: $MODE"
    log_info "Config: $CONFIG_FILE"
    log_info "Log: $LOG_FILE"
    echo ""

    # Verifica dependências
    check_dependencies

    # Executa testes conforme modo
    case "$MODE" in
        --full)
            log_info "Executando TODOS os testes (pipeline completo)..."
            test_old_pipeline
            test_new_scripts
            test_integration
            ;;
        --quick)
            log_info "Executando teste RÁPIDO (apenas scripts novos)..."
            test_new_scripts
            test_integration
            ;;
        --new-only)
            log_info "Executando apenas NOVOS scripts..."
            test_new_scripts
            ;;
        *)
            log_error "Modo inválido: $MODE"
            log_info "Uso: $0 [--full|--quick|--new-only]"
            exit 1
            ;;
    esac

    # Relatório final
    print_summary
}

# Executa
main "$@"
