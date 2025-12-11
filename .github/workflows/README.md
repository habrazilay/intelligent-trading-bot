# GitHub Actions Workflows

Workflows automatizados para pipeline de trading no Azure.

## 📁 Estrutura

```
.github/workflows/
├── pipeline-full.yml              # Pipeline completo (merge → predict)
├── step-merge-features.yml        # Step: Merge + Features
├── step-labels.yml                # Step: Generate Labels
├── step-train.yml                 # Step: Train Models
├── step-predict-signals.yml       # Step: Predict + Signals
├── schedule-weekly-download.yml   # Scheduled: Download semanal
├── build-push-docker-image.yml    # Build & Push Docker para ACR
└── README.md                      # Esta documentação
```

## 🎯 Padrões de Nomenclatura

### Workflows:
- `pipeline-{name}.yml` - Orquestrador (chama steps)
- `step-{name}.yml` - Workflow reusável (1 tarefa específica)
- `schedule-{freq}-{task}.yml` - Cron jobs agendados

### Configs:
- `{symbol}_{timeframe}_{variant}.jsonc`
- Exemplos:
  - `btcusdt_1m_dev.jsonc` - Dev genérico
  - `btcusdt_5m_aggressive.jsonc` - Estratégia agressiva
  - `btcusdt_5m_orderflow.jsonc` - Com features orderflow

## 🔧 Variáveis Compartilhadas

### Azure Container Registry (ACR)
```yaml
ACR_LOGIN_SERVER: itbacr.azurecr.io
ACR_REPOSITORY: itb-bot
```

### Azure Resources
```yaml
AZURE_RESOURCE_GROUP: rg-itb-dev
AZURE_STORAGE_ACCOUNT: stitbdev
```

### File Shares (por timeframe)
```yaml
AZURE_FILE_SHARE: data-itb-1m    # Para configs *_1m_*
AZURE_FILE_SHARE: data-itb-5m    # Para configs *_5m_*
AZURE_FILE_SHARE: data-itb-1h    # Para configs *_1h_*
```

### Secrets Necessários
Configure em: **Settings → Secrets and variables → Actions**

```
AZURE_CREDENTIALS      # Service Principal JSON
ACR_USERNAME           # Azure Container Registry username
ACR_PASSWORD           # Azure Container Registry password
AZURE_STORAGE_KEY      # Storage account key
BINANCE_API_KEY        # Binance API key (read-only)
BINANCE_API_SECRET     # Binance API secret
```

## 🚀 Como Usar

### 1. Pipeline Completo

Executa: merge → features → labels → train → predict

```bash
# Via GitHub UI:
Actions → "ITB Trading Pipeline - Full" → Run workflow
  Config: configs/btcusdt_5m_aggressive.jsonc
  Image tag: latest

# Via gh CLI:
gh workflow run pipeline-full.yml \
  -f config_path=configs/btcusdt_5m_aggressive.jsonc \
  -f image_tag=latest
```

### 2. Download Semanal (Automático)

Executa toda **segunda-feira às 00:05 UTC**.

Manual:
```bash
gh workflow run schedule-weekly-download.yml \
  -f symbols=all \
  -f config_path=configs/btcusdt_1m_dev.jsonc \
  -f image_tag=latest
```

### 3. Build Docker Image

Antes de rodar pipelines, certifique-se de ter image atualizada:

```bash
gh workflow run build-push-docker-image.yml
```

### 4. Steps Individuais

Útil para re-rodar uma etapa específica:

```bash
# Só treinar
gh workflow run step-train.yml \
  -f config_path=configs/btcusdt_5m_aggressive.jsonc \
  -f image_tag=latest

# Só gerar features
gh workflow run step-merge-features.yml \
  -f config_path=configs/btcusdt_5m_aggressive.jsonc \
  -f image_tag=latest
```

## 📊 Fluxo de Dados

```
┌─────────────────────────────────────────────────┐
│ 1. Download (Semanal)                           │
│    Binance API → Azure File Share               │
│    Output: DATA_ITB_*/BTCUSDT/klines.parquet    │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 2. Merge + Features                             │
│    klines.parquet → features.csv                │
│    Generators: TA-Lib, spread, regime           │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 3. Labels                                       │
│    features.csv → matrix.csv                    │
│    Labels: high_040_4, low_040_4                │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 4. Train                                        │
│    matrix.csv → MODELS/                         │
│    Algorithm: LightGBM                          │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 5. Predict + Signals                            │
│    MODELS/ + matrix.csv → signals.csv           │
│    Ready for shadow mode testing                │
└─────────────────────────────────────────────────┘
```

## 🔒 Ambiente Dev (Read-Only)

**Importante:** Workflows em `dev` apenas **leem** dados da Binance.

- ✅ Download histórico OHLCV (read-only API)
- ✅ Processar/treinar em Azure ACI
- ❌ Não fazem trades (shadow mode só em staging/prod)

## 🐳 Docker Image

Todos workflows usam imagem do ACR:
```
itbacr.azurecr.io/itb-bot:{image_tag}
```

**Tags disponíveis:**
- `latest` - Build mais recente
- `amd64-{timestamp}` - Builds específicos por arquitetura

**Build novo:**
```bash
# Automaticamente via workflow
gh workflow run build-push-docker-image.yml

# Ou manual
make docker-build
make docker-push
```

## 📝 Logs e Debug

### Ver logs de um workflow:
```bash
# Último run
gh run list --workflow=pipeline-full.yml --limit=1

# Ver logs
gh run view {run-id} --log
```

### Logs no Azure:
```bash
# Ver container logs
az container logs \
  --name itb-bot-merge-only \
  --resource-group rg-itb-dev
```

## 🔄 Versionamento

**Configs:**
- Versionados no Git
- Cada branch pode ter configs diferentes
- `main`: Produção stable
- `dev`: Experimentos

**Docker Images:**
- Tagueados com timestamp Unix
- `latest` sempre aponta para último build bem-sucedido

## 🚨 Troubleshooting

### Workflow falhou no step X:
1. Verificar logs: `gh run view {run-id} --log`
2. Testar localmente: `make {step} CONFIG=...`
3. Verificar Azure File Share tem dados

### Container não inicia:
1. Verificar secrets estão configurados
2. Verificar imagem existe no ACR
3. Verificar resource group existe

### Download não puxa dados novos:
1. Binance API rate limit (1200 req/min)
2. Verificar klines.parquet tem dados antigos
3. Script só baixa dados **novos** (incremental)

## 📚 Referências

- [GitHub Actions Reusable Workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows)
- [Azure Container Instances](https://docs.microsoft.com/en-us/azure/container-instances/)
- [Binance API Docs](https://binance-docs.github.io/apidocs/spot/en/)
