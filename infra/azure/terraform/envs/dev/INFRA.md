# Infraestrutura Azure - Intelligent Trading Bot

> **Autor:** Habrazilay
> **Role:** Senior DevOps Engineer
> **Implementação:** 100% autoral - do zero ao deploy em produção

---

## Resumo Executivo

Este documento descreve a infraestrutura cloud-native que **projetei e implementei do zero** para migrar o Intelligent Trading Bot de uma execução local para a **Microsoft Azure**.

O projeto original era executado manualmente em máquina local. Eu arquitetei e implementei toda a camada de infraestrutura, CI/CD e automação.

---

## O Que Eu Implementei

### 1. Infrastructure as Code (Terraform)

Criei toda a estrutura Terraform para provisionamento automatizado:

```
infra/azure/terraform/envs/dev/
├── main.tf          # Recursos principais (RG, Storage, File Share)
├── variables.tf     # Variáveis parametrizáveis
├── providers.tf     # Configuração do provider Azure
├── outputs.tf       # Outputs para integração
└── terraform.tfvars # Valores do ambiente dev
```

**Recursos provisionados:**

| Recurso | Nome | Especificação |
|---------|------|---------------|
| Resource Group | `rg-itb-dev` | Agrupamento lógico |
| Storage Account | `stitbdev` | Standard LRS, TLS 1.2 |
| File Share | `data-itb-1m` | 50 GB persistente |

### 2. Containerização (Docker)

Criei o `Dockerfile` otimizado para o projeto:

- **Base image:** Python 3.11-slim (menor footprint)
- **Multi-stage build ready:** Preparado para otimização futura
- **Layer caching:** Requirements primeiro para cache eficiente
- **Security:** Remoção de arquivos que conflitam com stdlib

### 3. CI/CD Pipeline (GitHub Actions)

Implementei **9 workflows** de automação:

| Workflow | Função | Tipo |
|----------|--------|------|
| `build-push-docker-image.yml` | Build e push para ACR | Trigger: push |
| `merge-only-aci.yml` | Merge + Features | Reusable workflow |
| `labels_new-only-aci.yml` | Geração de labels | Reusable workflow |
| `train-only-aci.yml` | Treinamento ML | Reusable workflow |
| `predict-signals-only-aci.yml` | Predição + Sinais | Reusable workflow |
| `dev-aci-pipeline-1m.yml` | **Pipeline completo orquestrado** | Orchestrator |
| `run-pipeline-aci-single.yml` | Pipeline em container único | Alternativo |
| `azure-functions-app-python.yml` | Deploy Azure Functions | Legacy |
| `dev-aks-helm.yml` | Deploy Kubernetes (AKS) | Futuro |

**Arquitetura do Pipeline:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    dev-aci-pipeline-1m.yml                      │
│                      (Orchestrator)                             │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ merge-only-aci  │→ │ labels-only-aci │→ │ train-only-aci  │
│                 │  │                 │  │                 │
│ • merge_new     │  │ • labels_new    │  │ • train         │
│ • features_new  │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ predict-signals │
                    │                 │
                    │ • predict       │
                    │ • signals       │
                    └─────────────────┘
```

### 4. Azure Container Instances (ACI)

Configurei execução serverless com:

- **CPU:** 1 core por job
- **Memória:** 2 GB por job
- **Restart Policy:** Never (jobs efêmeros)
- **Storage Mount:** Azure File Share em `/app/DATA_ITB_1m`
- **Registry:** Azure Container Registry (ACR) privado

### 5. Helm Charts (Kubernetes-ready)

Preparei charts Helm para futura migração AKS:

```
helm/intelligent-trading-bot/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── deployment.yaml
    ├── service.yaml
    ├── configmap.yaml
    └── secret-env.yaml
```

### 6. Refatoração de Scripts

Refatorei os scripts de ML para cloud:

| Script Original | Novo Script | Melhorias |
|-----------------|-------------|-----------|
| `merge.py` | `merge_new.py` | Logging estruturado, Parquet |
| `features.py` | `features_new.py` | Config-driven, progress bar |
| `labels.py` | `labels_new.py` | Incremental processing |

### 7. Secrets Management

Implementei gestão segura de credenciais:

- **GitHub Secrets** para CI/CD
- **Azure File Share** com chave segura
- **ACR** com autenticação via secrets
- `.env` no `.gitignore` (nunca commitado)

---

## Próximas Implementações

### 1. Azure Key Vault (Em desenvolvimento)

Migração de GitHub Secrets para Azure Key Vault:

```hcl
# A ser implementado
resource "azurerm_key_vault" "kv" {
  name                = "kv-itb-dev"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku_name            = "standard"
  tenant_id           = data.azurerm_client_config.current.tenant_id
}

resource "azurerm_key_vault_secret" "binance_api_key" {
  name         = "binance-api-key"
  value        = var.binance_api_key
  key_vault_id = azurerm_key_vault.kv.id
}
```

**Benefícios:**
- Rotação automática de secrets
- Audit logs completos
- RBAC granular
- Integração nativa com ACI

### 2. Download Direto Binance → Azure (Em desenvolvimento)

Eliminação do download local:

```
ANTES:  Binance API → Máquina Local → Upload → Azure Storage
DEPOIS: Binance API → Azure Container → Azure Storage (direto)
```

**Implementação:**
- Azure Container Instance dedicado para download
- Scheduled trigger (cron) ou Event-based
- Dados salvos diretamente no File Share

### 3. Azure Machine Learning (Roadmap)

- Treinamento gerenciado
- Hyperparameter tuning
- Model registry
- A/B testing de modelos

---

## Comandos Terraform

```bash
# Inicializar
cd infra/azure/terraform/envs/dev
terraform init

# Planejar mudanças
terraform plan

# Aplicar
terraform apply

# Destruir (cuidado!)
terraform destroy
```

---

## Custos Estimados

| Recurso | Custo Mensal | Notas |
|---------|--------------|-------|
| Storage Account (50GB) | ~$1.50 | LRS, Standard |
| ACI (jobs esporádicos) | ~$5-15 | Pay-per-second |
| ACR (Basic) | ~$5 | Registry de imagens |
| Key Vault (futuro) | ~$0.03/10k ops | Quase zero |
| **Total estimado** | **~$15-25/mês** | Muito menor que VM 24/7 |

---

## Competências Demonstradas

- **Infrastructure as Code:** Terraform, HCL
- **Containerização:** Docker, multi-stage builds
- **CI/CD:** GitHub Actions, reusable workflows
- **Cloud Azure:** ACI, ACR, Storage, Key Vault
- **Kubernetes:** Helm charts, AKS-ready
- **Security:** Secrets management, RBAC, TLS
- **DevOps Practices:** GitOps, IaC, automation

---

## Autor

**Habrazilay** - Senior DevOps Engineer

Toda esta infraestrutura foi projetada e implementada por mim, do zero, demonstrando competências full-stack em DevOps e Cloud Architecture.

- GitHub: [github.com/habrazilay](https://github.com/habrazilay)
- Projeto: [intelligent-trading-bot](https://github.com/habrazilay/intelligent-trading-bot)
