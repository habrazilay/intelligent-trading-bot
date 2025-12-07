# INFRA.md - Infraestrutura do Projeto Intelligent Trading Bot

> **Autor:** Habrazilay
> **Role:** Senior DevOps Engineer
> **Implementacao:** 100% autoral - do zero ao deploy em producao

Documento oficial da infraestrutura do projeto.
Mantido no branch dev.
Objetivo: garantir reprodutibilidade, previsibilidade e continuidade operacional.

---

## 1. Arquitetura Geral

A infraestrutura atual opera no modelo:

```
Local Dev -> Azure Dev (ACI + Storage) -> Staging Shadow Mode -> Futuro Prod Live Trading
```

A plataforma usa:
- Azure Storage Account para datasets versionados (Parquet, CSV, modelos).
- Azure Container Registry (ACR) para imagens Docker do bot e pipelines.
- Azure Container Instances (ACI) para rodar pipelines offline (treino, merge, labels, predict).
- Azure Key Vault para gestao segura de secrets (Binance API keys).
- Recovery Services Vault para backup diario dos dados criticos.
- Terraform para provisionamento da infraestrutura base.
- Terragrunt para configuracao DRY multi-cloud (Azure + GCP).

---

## 2. Recursos Azure

### 2.1 Resource Group (RG)

**Nome:** `rg-itb-dev`
**Funcao:** Agrupar todos os recursos do ambiente de desenvolvimento e staging.

---

### 2.2 Storage Account

**Nome:** `stitbdev`
**Tipo:** StorageV2
**Localizacao:** eastus

**Usos:**
- Armazenamento de datasets versionados (1m, 5m, 1h).
- Armazenamento dos modelos treinados.
- Armazenamento de sinais, matrizes e features.
- Fonte de dados para pipelines de treino em ACI.

**Acesso:**
- Chave primaria habilitada
- Public Network Access: Enabled
- TLS 1.2

---

### 2.3 File Shares

Estrutura atual:

| File share      | Proposito                     |
|-----------------|-------------------------------|
| data-itb-1m     | Dataset BTCUSDT 1m            |
| data-itb-5m     | Dataset BTCUSDT 5m            |
| data-itb-1h     | Dataset BTCUSDT 1h            |

Padrao interno:

```
<share-name>/
  BTCUSDT/
    vYYYY-MM-DD/
      klines.parquet
      features.csv
      matrix.csv
      predictions.csv
      predictions.txt
      signals.csv
      signal_models.txt
      Archive.zip
      MODELS/
        *.pickle
        *.scaler
```

---

### 2.4 Azure Container Registry (ACR)

**Nome:** `itbacr`
**Login server:** `itbacr.azurecr.io`
**SKU:** Basic
**Admin user:** Enabled

**Usos:**
- Armazenar imagens Docker para:
  - Pipelines dev
  - Merge/Labels/Predict
  - Staging
  - Futuro Prod

**Convencao de tags:**

```
itbacr.azurecr.io/itb-bot:<branch>-<commit>
itbacr.azurecr.io/itb-bot:dev-latest
itbacr.azurecr.io/itb-bot:staging-latest
```

---

### 2.5 Azure Key Vault

**Nome:** `kv-itbdev`
**SKU:** Standard

**Secrets gerenciados:**
- `binance-api-key`
- `binance-secret-key`

**Beneficios:**
- Rotacao automatica de secrets
- Audit logs completos
- RBAC granular
- Integracao nativa com ACI

---

### 2.6 Recovery Services Vault

**Nome:** `vault697`
**Localizacao:** `eastus`

**Politica:**
- Frequencia: diaria
- Horario: 19:30 UTC
- Retencao: 30 dias

**File shares protegidos:**
- `data-itb-1m`
- `data-itb-5m`
- `data-itb-1h`

---

## 3. Provisionamento (Terraform)

Local dos arquivos:

```
infra/azure/terraform/envs/dev
```

Comandos:

```
terraform init
terraform plan
terraform apply
```

Recursos gerenciados:
- Resource Group
- Storage Account
- File Shares (1m, 5m, 1h)
- Container Registry (importado)
- Key Vault

---

## 4. Pipelines CI/CD (GitHub Actions)

Pipelines principais:

- `dev-aci-pipeline-1m.yml` - roda merge -> features -> labels -> train -> predict -> signals
- `merge-only-aci.yml`
- `labels_new-only-aci.yml`
- `train-only-aci.yml`
- `predict-signals-only-aci.yml`
- `simulate-only.yml`
- `download-binance-azure.yml` - download direto Binance -> Azure

Pipelines separados facilitam debug e testes A/B.

---

## 5. Versionamento de Datasets

Parquets e artefatos sao versionados seguindo:

```
vYYYY-MM-DD
```

Exemplo:

```
data-itb-1m/BTCUSDT/v2025-12-05/
```

Isso garante:
- Reprodutibilidade
- Comparacao entre versoes
- Possibilidade de treinar modelos com datasets historicos precisos

---

## 6. Upload de datasets (Makefile + Scripts)

Scripts:

```
tools/upload_1m_parquet.sh
tools/upload_5m_parquet.sh
tools/upload_1h_parquet.sh
```

Makefile:

```
make upload-1m
make upload-5m
make upload-1h
```

Os scripts:
- Criam a pasta versionada
- Fazem upload via `az storage file upload-batch`
- Exibem os links dos arquivos enviados

---

## 7. Docker

Dockerfile:

- Base Python 3.11 Slim
- Instala dependencias
- Copia scripts e modulos

Build local:

```
docker build -t itb-bot:local .
```

Push para ACR:

```
docker tag itb-bot:local itbacr.azurecr.io/itb-bot:dev-latest
docker push itbacr.azurecr.io/itb-bot:dev-latest
```

---

## 8. Ambientes

### DEV
- Rodado localmente ou em ACI
- Usado para gerar parquets, treinar modelos, ajustar configs

### STAGING (shadow mode)
Executado local:

```
ENABLE_LIVE_TRADING=true python -m service.server -c configs/btcusdt_1m_staging_v2.jsonc
ENABLE_LIVE_TRADING=true python -m service.server -c configs/btcusdt_5m_staging_v2.jsonc
```

Objetivo:
- Emitir BUY/SELL reais
- Nao executar trades
- Gerar logs analisaveis

### PROD (futuro)
- Config dedicado
- Execucao em ACI ou Azure Container Apps
- Observabilidade completa

---

## 9. Logs & Analytics

Estrutura:

```
logs/raw/
logs/analytics/
logs/server_1m_*.log
logs/server_5m_*.log
```

Scripts:

```
parse_staging_logs.py
analyze_btcusdt_1m.py
analyze_btcusdt_5m.py
analyze_btcusdt_1h.py
```

Resultados:
- JSON automatico em `logs/analytics/`
- Arquivos `.result.txt` para leitura humana

---

## 10. Roadmap Infra

### Ja feito
- Backup diario
- Versionamento completo dos datasets
- Upload automatizado
- Pipelines dev rodando em ACI
- Staging shadow mode
- Key Vault para secrets
- Terragrunt para multi-cloud

### Proximos passos
- Criar banco PostgreSQL para armazenar:
  - PnL
  - Sinais
  - Metricas de modelo
- Mover Recovery Vault para Terraform
- Criar ambiente PROD
- GCP Vertex AI para ML training

---

## 11. Comandos uteis

Login:

```
az login
az account set --subscription "Azure subscription 1"
```

Upload:

```
make upload-1m VERSION=v2025-12-05
```

Rodar staging:

```
make staging-1m
make staging-5m
```

Pipeline dev:

```
make dev-1m
make dev-5m
```

---

## Custos Estimados

| Recurso | Custo Mensal | Notas |
|---------|--------------|-------|
| Storage Account (50GB) | ~$1.50 | LRS, Standard |
| ACI (jobs esporadicos) | ~$5-15 | Pay-per-second |
| ACR (Basic) | ~$5 | Registry de imagens |
| Key Vault | ~$0.03/10k ops | Quase zero |
| **Total estimado** | **~$15-25/mes** | Muito menor que VM 24/7 |

---

Documento finalizado.
Pronto para auditoria, evolucao e colaboracao profissional.
