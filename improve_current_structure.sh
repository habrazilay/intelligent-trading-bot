#!/bin/bash
# Script para melhorias INCREMENTAIS na sua estrutura atual
# SEM reorganizar tudo, apenas adicionar o que falta

set -e

REPO="/Users/danielschmidt/intelligent-trading-bot"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================="
echo "🎨 Melhorias na Estrutura Atual"
echo "========================================="
echo ""

echo "Sua estrutura atual está ótima!"
echo "Este script adiciona pequenas melhorias SEM reorganizar tudo."
echo ""

echo "Melhorias disponíveis:"
echo ""
echo "1) Adicionar versionamento de modelos (dentro de MODELS/)"
echo "2) Organizar logs analytics por mês (logs/analytics/2024-12/)"
echo "3) Criar metadata para experiments"
echo "4) Criar backup incremental dos dados importantes"
echo "5) Ver estatísticas da estrutura atual"
echo "6) Sair"
echo ""
read -p "Escolha (1-6): " choice

case $choice in
    1)
        echo -e "${YELLOW}Adicionando versionamento de modelos...${NC}"

        for models_dir in "$REPO"/DATA_ITB_*/*/MODELS; do
            if [ -d "$models_dir" ]; then
                echo "Processando: $models_dir"

                # Criar pasta v1 com modelos atuais
                mkdir -p "$models_dir/v1_$TIMESTAMP"

                # Mover modelos atuais para v1
                for f in "$models_dir"/*.pickle "$models_dir"/*.scaler 2>/dev/null; do
                    [ -f "$f" ] && mv "$f" "$models_dir/v1_$TIMESTAMP/"
                done

                # Criar symlink 'current'
                ln -sf "v1_$TIMESTAMP" "$models_dir/current"

                # Criar metadata
                cat > "$models_dir/v1_$TIMESTAMP/metadata.json" <<EOF
{
  "version": "v1_$TIMESTAMP",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "description": "Initial model version (migrated from flat structure)"
}
EOF

                echo -e "${GREEN}✓ Versionado: $models_dir${NC}"
            fi
        done

        echo ""
        echo -e "${GREEN}✓ Modelos versionados!${NC}"
        echo "Use 'current' symlink para acessar versão ativa"
        ;;

    2)
        echo -e "${YELLOW}Organizando logs analytics por mês...${NC}"

        analytics_dir="$REPO/logs/analytics"
        if [ -d "$analytics_dir" ]; then
            # Criar estrutura por ano/mês
            mkdir -p "$analytics_dir/2024-12"
            mkdir -p "$analytics_dir/archive"

            # Mover arquivos existentes para o mês correto
            for f in "$analytics_dir"/*.json; do
                if [ -f "$f" ]; then
                    # Extrair data do nome do arquivo
                    if [[ $(basename "$f") =~ ([0-9]{4})-([0-9]{2})-([0-9]{2}) ]]; then
                        year="${BASH_REMATCH[1]}"
                        month="${BASH_REMATCH[2]}"

                        mkdir -p "$analytics_dir/$year-$month"
                        mv "$f" "$analytics_dir/$year-$month/"

                        echo "Movido: $(basename $f) → $year-$month/"
                    fi
                fi
            done

            echo -e "${GREEN}✓ Logs organizados por mês!${NC}"
        else
            echo "Pasta logs/analytics não encontrada"
        fi
        ;;

    3)
        echo -e "${YELLOW}Criando metadata para experiments...${NC}"

        exp_dir="$REPO/experiments/results"
        if [ -d "$exp_dir" ]; then
            for result in "$exp_dir"/*.json; do
                if [ -f "$result" ]; then
                    metadata="${result%.json}.metadata.json"

                    if [ ! -f "$metadata" ]; then
                        # Criar metadata básica
                        cat > "$metadata" <<EOF
{
  "result_file": "$(basename $result)",
  "created_at": "$(date -r "$result" -u +%Y-%m-%dT%H:%M:%SZ)",
  "file_size_bytes": $(stat -f%z "$result"),
  "experiment_type": "model_training",
  "notes": "Add your notes here"
}
EOF
                        echo "Criado: $(basename $metadata)"
                    fi
                fi
            done

            echo -e "${GREEN}✓ Metadata criada!${NC}"
        fi
        ;;

    4)
        echo -e "${YELLOW}Criando backup incremental...${NC}"

        backup_dir="$REPO/BACKUPS/$TIMESTAMP"
        mkdir -p "$backup_dir"

        # Backup de arquivos pequenos importantes
        echo "Copiando configs..."
        cp -r "$REPO/configs" "$backup_dir/"

        echo "Copiando modelos..."
        for models in "$REPO"/DATA_ITB_*/*/MODELS; do
            if [ -d "$models" ]; then
                rel_path="${models#$REPO/}"
                mkdir -p "$backup_dir/$(dirname $rel_path)"
                cp -r "$models" "$backup_dir/$rel_path"
            fi
        done

        echo "Copiando transactions..."
        find "$REPO/DATA_ITB_"* -name "transactions.txt" -exec cp --parents {} "$backup_dir/" \; 2>/dev/null || true

        echo "Copiando logs analytics..."
        [ -d "$REPO/logs/analytics" ] && cp -r "$REPO/logs/analytics" "$backup_dir/"

        echo "Copiando experiments results..."
        [ -d "$REPO/experiments/results" ] && cp -r "$REPO/experiments/results" "$backup_dir/"

        # Criar README no backup
        cat > "$backup_dir/README.md" <<EOF
# Backup - $TIMESTAMP

Criado: $(date)

## Conteúdo
- configs/
- MODELS/ (todos os modelos treinados)
- transactions.txt (histórico de trades)
- logs/analytics/
- experiments/results/

## Tamanho Total
$(du -sh "$backup_dir" | cut -f1)

## Restaurar
Para restaurar, copie os arquivos de volta para as pastas originais.
EOF

        echo ""
        echo -e "${GREEN}✓ Backup criado em:${NC}"
        echo "  $backup_dir"
        echo ""
        du -sh "$backup_dir"
        ;;

    5)
        echo -e "${BLUE}Estatísticas da Estrutura Atual${NC}"
        echo "========================================="
        echo ""

        echo "📊 Tamanho por pasta DATA:"
        du -sh "$REPO"/DATA_ITB_* 2>/dev/null
        echo ""

        echo "🤖 Modelos treinados:"
        find "$REPO"/DATA_ITB_* -name "*.pickle" | wc -l | xargs echo "Total:"
        find "$REPO"/DATA_ITB_* -name "*.pickle" -ls 2>/dev/null
        echo ""

        echo "💰 Transações registradas:"
        for tx in "$REPO"/DATA_ITB_*/*/transactions.txt; do
            if [ -f "$tx" ]; then
                lines=$(wc -l < "$tx")
                echo "$(dirname $tx): $lines transações"
            fi
        done
        echo ""

        echo "📝 Logs:"
        echo "Raw logs: $(find "$REPO/logs/raw" -type f 2>/dev/null | wc -l) arquivos"
        echo "Analytics: $(find "$REPO/logs/analytics" -type f 2>/dev/null | wc -l) arquivos"
        echo ""

        echo "🧪 Experimentos:"
        echo "Results: $(find "$REPO/experiments/results" -name "*.json" 2>/dev/null | wc -l) resultados"
        echo ""

        echo "⚙️ Configs:"
        echo "Total: $(find "$REPO/configs" -name "*.jsonc" | wc -l) configs"
        echo "Dev: $(find "$REPO/configs" -name "*_dev.jsonc" | wc -l)"
        echo "Staging: $(find "$REPO/configs" -name "*_staging*.jsonc" | wc -l)"
        echo "Samples: $(find "$REPO/configs/samples" -name "*.jsonc" 2>/dev/null | wc -l)"
        ;;

    6)
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
