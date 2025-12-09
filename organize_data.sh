#!/bin/bash
# Script de Organização de Dados - PRESERVA TUDO, apenas organiza

set -e

REPO="/Users/danielschmidt/intelligent-trading-bot"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
YEAR=$(date +%Y)
MONTH=$(date +%m)

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================="
echo "🏆 Organização de Dados"
echo "========================================="
echo ""
echo "Filosofia: NUNCA deletar dados!"
echo "Apenas organizar e preservar."
echo ""

# Verificar o que existe
echo -e "${BLUE}Estrutura atual:${NC}"
ls -lh "$REPO" | grep DATA || echo "Nenhuma pasta DATA encontrada"
echo ""

echo "O que você quer fazer?"
echo ""
echo "1) Criar estrutura organizada (DATA_STAGING, DATA_ARCHIVE, DATA_EXPERIMENTS)"
echo "2) Arquivar dados atuais (move DATA_ITB_* para DATA_ARCHIVE)"
echo "3) Ver relatório de dados existentes"
echo "4) Criar pasta para novo experimento"
echo "5) Sair"
echo ""
read -p "Escolha (1-5): " choice

case $choice in
    1)
        echo -e "${YELLOW}Criando estrutura organizada...${NC}"

        # Criar estrutura
        mkdir -p "$REPO/DATA_ARCHIVE/$YEAR/$MONTH"
        mkdir -p "$REPO/DATA_STAGING/btcusdt_1m"/{raw,processed,models,logs,transactions,performance}
        mkdir -p "$REPO/DATA_STAGING/btcusdt_5m"/{raw,processed,models,logs,transactions,performance}
        mkdir -p "$REPO/DATA_STAGING/btcusdt_1h"/{raw,processed,models,logs,transactions,performance}
        mkdir -p "$REPO/DATA_EXPERIMENTS"

        echo -e "${GREEN}✓ Estrutura criada!${NC}"
        echo ""
        echo "Estrutura:"
        tree -L 2 "$REPO/DATA_STAGING" 2>/dev/null || ls -R "$REPO/DATA_STAGING"
        ;;

    2)
        echo -e "${YELLOW}Arquivando dados atuais...${NC}"
        echo "Dados serão MOVIDOS (não deletados) para DATA_ARCHIVE"
        echo ""

        read -p "Continuar? (s/N): " confirm
        if [ "$confirm" != "s" ] && [ "$confirm" != "S" ]; then
            echo "Cancelado."
            exit 0
        fi

        # Criar pasta de arquivo
        mkdir -p "$REPO/DATA_ARCHIVE/$YEAR/$MONTH"

        # Mover dados atuais
        for dir in "$REPO"/DATA_ITB_*; do
            if [ -d "$dir" ]; then
                dirname=$(basename "$dir")
                echo "Arquivando $dirname..."
                mv "$dir" "$REPO/DATA_ARCHIVE/$YEAR/$MONTH/${dirname}_archived_$TIMESTAMP"
            fi
        done

        echo -e "${GREEN}✓ Dados arquivados em:${NC}"
        echo "  $REPO/DATA_ARCHIVE/$YEAR/$MONTH/"
        ;;

    3)
        echo -e "${BLUE}Relatório de Dados${NC}"
        echo "========================================="
        echo ""

        echo "📊 Espaço total usado:"
        du -sh "$REPO"/DATA* 2>/dev/null || echo "Nenhuma pasta DATA encontrada"
        echo ""

        echo "📁 Detalhes por pasta:"
        for dir in "$REPO"/DATA*/; do
            if [ -d "$dir" ]; then
                echo ""
                echo "$(basename $dir):"
                du -sh "$dir"/* 2>/dev/null | sort -hr | head -10
            fi
        done
        echo ""

        echo "🗃️ Arquivos Parquet (dados brutos):"
        find "$REPO"/DATA* -name "*.parquet" -exec du -sh {} \; 2>/dev/null | sort -hr
        echo ""

        echo "🤖 Modelos treinados:"
        find "$REPO"/DATA* -name "*.pickle" -o -name "*.pkl" 2>/dev/null
        echo ""

        echo "💰 Arquivos de transações:"
        find "$REPO"/DATA* -name "transactions.txt" -exec wc -l {} \; 2>/dev/null
        ;;

    4)
        echo -e "${YELLOW}Criar pasta para novo experimento${NC}"
        echo ""

        read -p "Nome do experimento (ex: rsi_sma_test): " exp_name
        if [ -z "$exp_name" ]; then
            echo "Nome não pode ser vazio."
            exit 1
        fi

        exp_dir="$REPO/DATA_EXPERIMENTS/exp_${exp_name}_$TIMESTAMP"
        mkdir -p "$exp_dir"/{raw,processed,models,logs,results}

        echo -e "${GREEN}✓ Experimento criado em:${NC}"
        echo "  $exp_dir"
        echo ""
        echo "Próximos passos:"
        echo "1. Crie um config em configs/experiments/exp_${exp_name}.jsonc"
        echo "2. Configure: \"data_folder\": \"./DATA_EXPERIMENTS/exp_${exp_name}_$TIMESTAMP\""
        echo "3. Rode: python -m scripts.download_binance -c configs/experiments/exp_${exp_name}.jsonc"
        ;;

    5)
        echo "Saindo."
        exit 0
        ;;

    *)
        echo "Opção inválida."
        exit 1
        ;;
esac

echo ""
echo "========================================="
echo -e "${GREEN}Concluído!${NC}"
echo "========================================="
