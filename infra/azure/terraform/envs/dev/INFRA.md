🌐 INFRA.md – Infraestrutura do Projeto Intelligent Trading Bot

Documento oficial da infraestrutura do projeto.
Mantido no branch dev.
Objetivo: garantir reprodutibilidade, previsibilidade e continuidade operacional.

---

📌 1. Arquitetura Geral

A infraestrutura atual opera no modelo:

Local Dev → Azure Dev (ACI + Storage) → Staging Shadow Mode → Futuro Prod Live Trading

A plataforma usa:
- Azure Storage Account para datasets versionados (Parquet, CSV, modelos).
- Azure Container Registry (ACR) para imagens Docker do bot e pipelines.
- Azure Container Instances (ACI) para rodar pipelines offline (treino, merge, labels, predict).
- Recovery Services Vault para backup diário dos dados críticos.
- Terraform para provisionamento da infraestrutura base.

---

🗂️ 2. Recursos Azure

### 2.1 Resource Group (RG)

**Nome:** `rg-itb-dev`  
**Função:** Agrupar todos os recursos do ambiente de desenvolvimento e staging.

---

### 2.2 Storage Account

**Nome:** `stitbdev`  
**Tipo:** StorageV2  
**Localização:** eastus  

**Usos:**
- Armazenamento de datasets versionados (1m, 5m, 1h).
- Armazenamento dos modelos treinados.
- Armazenamento de sinais, matrizes e features.
- Fonte de dados para pipelines de treino em ACI.

**Acesso:**
- Chave primária habilitada  
- Public Network Access: Enabled  
- TLS 1.2  

---

### 2.3 File Shares

Estrutura atual:

| File share      | Propósito                     |
|-----------------|-------------------------------|
| data-itb-1m     | Dataset BTCUSDT 1m            |
| data-itb-5m     | Dataset BTCUSDT 5m            |
| data-itb-1h     | Dataset BTCUSDT 1h            |

Padrão interno:

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

**Convenção de tags:**

```
itbacr.azurecr.io/itb-bot:<branch>-<commit>
itbacr.azurecr.io/itb-bot:dev-latest
itbacr.azurecr.io/itb-bot:staging-latest
```

---

### 2.5 Recovery Services Vault

**Nome:** `vault697`  
**Localização:** `eastus`

**Política:**
- Frequência: diária
- Horário: 19:30 UTC
- Retenção: 30 dias

**File shares protegidos:**
- `data-itb-1m`
- `data-itb-5m`
- `data-itb-1h`

---

🛠️ 3. Provisionamento (Terraform)

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

⚠️ O Recovery Services Vault ainda não está sob Terraform.

---

🚀 4. Pipelines CI/CD (GitHub Actions)

Pipelines principais:

- `dev-aci-pipeline-1m.yml` – roda merge → features → labels → train → predict → signals  
- `merge-only-aci.yml`  
- `labels_new-only-aci.yml`  
- `train-only-aci.yml`  
- `predict-signals-only-aci.yml`  
- `simulate-only.yml`  

Pipelines separados facilitam debug e testes A/B.

---

📊 5. Versionamento de Datasets

Parquets e artefatos são versionados seguindo:

```
vYYYY-MM-DD
```

Exemplo:

```
data-itb-1m/BTCUSDT/v2025-12-05/
```

Isso garante:
- Reprodutibilidade  
- Comparação entre versões  
- Possibilidade de treinar modelos com datasets históricos precisos  

---

📦 6. Upload de datasets (Makefile + Scripts)

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

🐳 7. Docker

Dockerfile:

- Base Python 3.11 Slim
- Instala dependências
- Copia scripts e módulos

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

🧪 8. Ambientes

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
- Não executar trades
- Gerar logs analisáveis

### PROD (futuro)
- Config dedicado
- Execução em ACI ou Azure Container Apps
- Observabilidade completa

---

📈 9. Logs & Analytics

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
- JSON automático em `logs/analytics/`
- Arquivos `.result.txt` para leitura humana

---

🧠 10. Roadmap Infra

### ✔️ Já feito
- Backup diário
- Versionamento completo dos datasets
- Upload automatizado
- Pipelines dev rodando em ACI
- Staging shadow mode

### 🔜 Próximos passos
- Criar banco PostgreSQL para armazenar:
  - PnL  
  - Sinais  
  - Métricas de modelo  
- Mover Recovery Vault para Terraform
- Criar ambiente PROD

---

🧩 11. Comandos úteis

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

✔️ Documento finalizado.

Pronto para auditoria, evolução e colaboração profissional.