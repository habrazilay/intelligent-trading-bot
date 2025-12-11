#!/bin/bash
###############################################################################
# Azure Setup Helper Script
#
# Automatiza a configuração da Azure para CI/CD
#
# Uso:
#   ./setup_azure.sh [--interactive|--check|--destroy]
#
###############################################################################

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configurações (edite conforme necessário)
RESOURCE_GROUP="rg-trading-bot"
LOCATION="eastus"
STORAGE_ACCOUNT="sttradinbot$(date +%s | tail -c 6)"  # Nome único
CONTAINER_NAME="models"
SP_NAME="GitHub-Actions-Trading-Bot"

# Funções
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

section() {
    echo ""
    echo "================================================================="
    echo "  $1"
    echo "================================================================="
}

check_az_cli() {
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI não encontrado!"
        log_info "Instale: https://docs.microsoft.com/cli/azure/install-azure-cli"
        exit 1
    fi

    log_success "Azure CLI encontrado: $(az version --query '"azure-cli"' -o tsv)"
}

check_logged_in() {
    if ! az account show &> /dev/null; then
        log_error "Não está logado na Azure!"
        log_info "Execute: az login"
        exit 1
    fi

    ACCOUNT=$(az account show --query name -o tsv)
    SUBSCRIPTION_ID=$(az account show --query id -o tsv)
    log_success "Logado como: $ACCOUNT"
    log_info "Subscription ID: $SUBSCRIPTION_ID"
}

###############################################################################
# Verificar status atual
###############################################################################

check_status() {
    section "Verificando Status Atual"

    check_az_cli
    check_logged_in

    # Resource Group
    if az group exists --name "$RESOURCE_GROUP" --output tsv | grep -q true; then
        log_success "Resource Group '$RESOURCE_GROUP' existe"
    else
        log_warning "Resource Group '$RESOURCE_GROUP' NÃO existe"
    fi

    # Storage Account (tentar listar)
    STORAGE_EXISTS=$(az storage account list --resource-group "$RESOURCE_GROUP" --query "[?contains(name, 'sttradinbot')].name" -o tsv 2>/dev/null || echo "")
    if [ -n "$STORAGE_EXISTS" ]; then
        log_success "Storage Account encontrada: $STORAGE_EXISTS"
        STORAGE_ACCOUNT="$STORAGE_EXISTS"
    else
        log_warning "Nenhuma Storage Account encontrada"
    fi

    # Service Principal
    SP_EXISTS=$(az ad sp list --display-name "$SP_NAME" --query "[].appId" -o tsv 2>/dev/null || echo "")
    if [ -n "$SP_EXISTS" ]; then
        log_success "Service Principal '$SP_NAME' existe"
        log_info "App ID: $SP_EXISTS"
    else
        log_warning "Service Principal '$SP_NAME' NÃO existe"
    fi

    echo ""
    log_info "Para criar recursos faltantes, execute: ./setup_azure.sh --interactive"
}

###############################################################################
# Setup interativo
###############################################################################

setup_interactive() {
    section "Setup Interativo da Azure"

    check_az_cli
    check_logged_in

    # Confirmar configurações
    echo ""
    log_info "Configurações:"
    echo "  Resource Group:    $RESOURCE_GROUP"
    echo "  Location:          $LOCATION"
    echo "  Storage Account:   $STORAGE_ACCOUNT"
    echo "  Service Principal: $SP_NAME"
    echo ""

    read -p "Continuar com essas configurações? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Abortado pelo usuário"
        exit 0
    fi

    # 1. Criar Resource Group
    section "1. Criando Resource Group"

    if az group exists --name "$RESOURCE_GROUP" --output tsv | grep -q true; then
        log_info "Resource Group já existe, pulando..."
    else
        log_info "Criando Resource Group '$RESOURCE_GROUP'..."
        az group create \
            --name "$RESOURCE_GROUP" \
            --location "$LOCATION" \
            --output table

        log_success "Resource Group criada!"
    fi

    # 2. Criar Storage Account
    section "2. Criando Storage Account"

    STORAGE_EXISTS=$(az storage account list --resource-group "$RESOURCE_GROUP" --query "[?contains(name, 'sttradinbot')].name" -o tsv 2>/dev/null || echo "")

    if [ -n "$STORAGE_EXISTS" ]; then
        log_info "Storage Account já existe: $STORAGE_EXISTS"
        STORAGE_ACCOUNT="$STORAGE_EXISTS"
    else
        log_info "Criando Storage Account '$STORAGE_ACCOUNT'..."
        az storage account create \
            --name "$STORAGE_ACCOUNT" \
            --resource-group "$RESOURCE_GROUP" \
            --location "$LOCATION" \
            --sku Standard_LRS \
            --output table

        log_success "Storage Account criada!"
    fi

    # 3. Criar Container
    section "3. Criando Container para Modelos"

    log_info "Criando container '$CONTAINER_NAME'..."
    az storage container create \
        --name "$CONTAINER_NAME" \
        --account-name "$STORAGE_ACCOUNT" \
        --output table || log_warning "Container pode já existir"

    log_success "Container criado!"

    # 4. Criar Service Principal
    section "4. Criando Service Principal"

    SP_EXISTS=$(az ad sp list --display-name "$SP_NAME" --query "[].appId" -o tsv 2>/dev/null || echo "")

    if [ -n "$SP_EXISTS" ]; then
        log_warning "Service Principal já existe!"
        log_info "App ID: $SP_EXISTS"
        log_warning "Se quiser recriar, primeiro delete:"
        log_warning "  az ad sp delete --id $SP_EXISTS"
        echo ""
        read -p "Gerar novas credenciais? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Pulando Service Principal..."
            SP_JSON=""
        else
            # Resetar credenciais
            log_info "Resetando credenciais do Service Principal..."
            SUBSCRIPTION_ID=$(az account show --query id -o tsv)

            SP_JSON=$(az ad sp create-for-rbac \
                --name "$SP_NAME" \
                --role contributor \
                --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
                --sdk-auth)
        fi
    else
        log_info "Criando Service Principal '$SP_NAME'..."
        SUBSCRIPTION_ID=$(az account show --query id -o tsv)

        SP_JSON=$(az ad sp create-for-rbac \
            --name "$SP_NAME" \
            --role contributor \
            --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
            --sdk-auth)

        log_success "Service Principal criado!"
    fi

    # 5. Mostrar resumo
    section "Setup Completo! 🎉"

    echo ""
    log_success "Recursos criados com sucesso!"
    echo ""

    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "PRÓXIMOS PASSOS - Configure GitHub Secrets"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    echo "1. Vá em: Settings → Secrets and variables → Actions"
    echo ""

    if [ -n "$SP_JSON" ]; then
        echo "2. Adicione o secret AZURE_CREDENTIALS:"
        echo ""
        echo "$SP_JSON"
        echo ""
    else
        echo "2. Secret AZURE_CREDENTIALS já existe ou foi pulado"
        echo ""
    fi

    echo "3. Adicione o secret AZURE_STORAGE_ACCOUNT:"
    echo ""
    echo "   $STORAGE_ACCOUNT"
    echo ""

    echo "4. Adicione outros secrets necessários:"
    echo "   - BINANCE_API_KEY"
    echo "   - BINANCE_API_SECRET"
    echo "   - TELEGRAM_BOT_TOKEN"
    echo "   - TELEGRAM_CHAT_ID"
    echo ""

    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Salvar em arquivo
    SECRETS_FILE="azure_secrets_$(date +%Y%m%d_%H%M%S).txt"
    {
        echo "Azure Secrets - $(date)"
        echo "================================="
        echo ""
        echo "AZURE_STORAGE_ACCOUNT:"
        echo "$STORAGE_ACCOUNT"
        echo ""
        if [ -n "$SP_JSON" ]; then
            echo "AZURE_CREDENTIALS:"
            echo "$SP_JSON"
        fi
    } > "$SECRETS_FILE"

    log_success "Secrets salvos em: $SECRETS_FILE"
    log_warning "⚠️  NÃO commite este arquivo! Ele contém credenciais sensíveis!"
    echo ""

    # Adicionar ao .gitignore
    if ! grep -q "azure_secrets_" .gitignore 2>/dev/null; then
        echo "azure_secrets_*.txt" >> .gitignore
        log_success "Adicionado ao .gitignore"
    fi
}

###############################################################################
# Destruir recursos (cleanup)
###############################################################################

destroy_resources() {
    section "Destruir Recursos da Azure"

    check_az_cli
    check_logged_in

    log_warning "⚠️  ATENÇÃO: Isso vai DELETAR todos os recursos criados!"
    log_warning "   - Resource Group: $RESOURCE_GROUP"
    log_warning "   - Todos os recursos dentro dela"
    log_warning "   - Service Principal: $SP_NAME"
    echo ""

    read -p "Tem CERTEZA que quer continuar? Digite 'DELETE' para confirmar: " CONFIRM

    if [ "$CONFIRM" != "DELETE" ]; then
        log_info "Abortado pelo usuário"
        exit 0
    fi

    # Deletar Service Principal
    SP_ID=$(az ad sp list --display-name "$SP_NAME" --query "[].appId" -o tsv 2>/dev/null || echo "")
    if [ -n "$SP_ID" ]; then
        log_info "Deletando Service Principal..."
        az ad sp delete --id "$SP_ID"
        log_success "Service Principal deletado"
    fi

    # Deletar Resource Group (deleta tudo dentro também)
    if az group exists --name "$RESOURCE_GROUP" --output tsv | grep -q true; then
        log_info "Deletando Resource Group (isso pode demorar)..."
        az group delete --name "$RESOURCE_GROUP" --yes --no-wait
        log_success "Resource Group deletion iniciada (rodando em background)"
    fi

    echo ""
    log_success "Cleanup iniciado!"
    log_info "Verifique o status com: az group show --name $RESOURCE_GROUP"
}

###############################################################################
# Main
###############################################################################

main() {
    MODE="${1:---check}"

    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║              Azure Setup Helper - Trading Bot                  ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""

    case "$MODE" in
        --check)
            check_status
            ;;
        --interactive)
            setup_interactive
            ;;
        --destroy)
            destroy_resources
            ;;
        *)
            log_error "Modo inválido: $MODE"
            echo ""
            log_info "Uso:"
            echo "  ./setup_azure.sh --check         # Verificar status atual"
            echo "  ./setup_azure.sh --interactive   # Setup completo interativo"
            echo "  ./setup_azure.sh --destroy       # Deletar recursos (cuidado!)"
            exit 1
            ;;
    esac
}

main "$@"
