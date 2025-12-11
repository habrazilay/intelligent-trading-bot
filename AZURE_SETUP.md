# Guia de Setup Azure CI/CD

## 📋 Índice
- [Visão Geral](#visão-geral)
- [Pré-requisitos](#pré-requisitos)
- [Configuração de Secrets](#configuração-de-secrets)
- [Estrutura do Workflow](#estrutura-do-workflow)
- [Como Usar](#como-usar)
- [Troubleshooting](#troubleshooting)

---

## Visão Geral

O workflow `azure-pipeline.yml` automatiza todo o pipeline de ML na Azure:

```
┌─────────────┐
│  1. Validate│  ← Valida código e dependências
└──────┬──────┘
       │
┌──────▼──────┐
│  2. Download│  ← Baixa dados da Binance
└──────┬──────┘
       │
┌──────▼──────────┐
│ 3. Feature Eng. │  ← Merge, Features, Labels
└──────┬──────────┘
       │
┌──────▼──────┐
│  4. Train   │  ← Treina modelos ML
└──────┬──────┘
       │
┌──────▼──────┐
│ 5. Validate │  ← Testa modelos
└──────┬──────┘
       │
┌──────▼──────┐
│ 6. Deploy   │  ← Deploy para Azure (só main)
└──────┬──────┘
       │
┌──────▼──────┐
│  7. Notify  │  ← Notifica via Telegram
└─────────────┘
```

---

## Pré-requisitos

### 1. Conta Azure

```bash
# Fazer login
az login

# Listar assinaturas
az account list --output table

# Definir assinatura ativa
az account set --subscription "SUBSCRIPTION_ID"
```

### 2. Criar Service Principal

```bash
# Criar SP com permissões de Contributor
az ad sp create-for-rbac \
  --name "GitHub-Actions-Trading-Bot" \
  --role contributor \
  --scopes /subscriptions/{SUBSCRIPTION_ID} \
  --sdk-auth

# Output será algo como:
{
  "clientId": "xxxx",
  "clientSecret": "xxxx",
  "subscriptionId": "xxxx",
  "tenantId": "xxxx",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  ...
}

# ⚠️ GUARDAR ESSE JSON! Será usado como secret AZURE_CREDENTIALS
```

### 3. Criar Azure Storage Account

```bash
# Criar Resource Group
az group create \
  --name rg-trading-bot \
  --location eastus

# Criar Storage Account
az storage account create \
  --name sttradinbotmodels \
  --resource-group rg-trading-bot \
  --location eastus \
  --sku Standard_LRS

# Pegar connection string
az storage account show-connection-string \
  --name sttradinbotmodels \
  --resource-group rg-trading-bot \
  --output tsv

# Criar container para modelos
az storage container create \
  --name models \
  --account-name sttradinbotmodels
```

---

## Configuração de Secrets

### GitHub Repository Secrets

Vá em: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

#### Secrets Obrigatórios

| Secret Name | Descrição | Como Obter |
|-------------|-----------|------------|
| `AZURE_CREDENTIALS` | Credenciais do Service Principal | JSON do `az ad sp create-for-rbac` |
| `AZURE_STORAGE_ACCOUNT` | Nome da Storage Account | Nome criado acima (ex: `sttradinbotmodels`) |
| `BINANCE_API_KEY` | Chave API da Binance | [Binance API Management](https://www.binance.com/en/my/settings/api-management) |
| `BINANCE_API_SECRET` | Secret da API Binance | Mesmo lugar acima |
| `TELEGRAM_BOT_TOKEN` | Token do bot Telegram | [@BotFather](https://t.me/botfather) |
| `TELEGRAM_CHAT_ID` | ID do chat Telegram | [@userinfobot](https://t.me/userinfobot) |

#### Secrets Opcionais

| Secret Name | Descrição | Default |
|-------------|-----------|---------|
| `AZURE_REGION` | Região da Azure | `eastus` |
| `PYTHON_VERSION` | Versão do Python | `3.10` |

---

## Estrutura do Workflow

### Jobs Detalhados

#### 1️⃣ **Validate**
- ✅ Valida sintaxe Python
- ✅ Instala dependências
- ✅ Verifica arquivos de config
- ✅ Roda linter (opcional)

**Quando roda**: Sempre

#### 2️⃣ **Download Data**
- 📥 Baixa dados históricos da Binance
- 📦 Salva como artifact

**Quando roda**:
- `workflow_dispatch` (manual)
- Commit message contém `[download]`

**Exemplo**:
```bash
git commit -m "feat: update strategy [download]"
```

#### 3️⃣ **Feature Engineering**
- 🔄 Merge de dados
- 🧮 Calcula features
- 🏷️ Gera labels
- 📦 Salva artifacts

**Quando roda**: Após download ou sempre (se download foi skipado)

#### 4️⃣ **Train Models**
- 🤖 Treina modelos ML (LightGBM, LogisticRegression, etc.)
- 📊 Gera métricas
- 💾 Salva modelos

**Quando roda**: Após feature engineering

#### 5️⃣ **Validate Models**
- 🔮 Gera predições
- 📈 Cria sinais de trading
- ✅ Valida performance

**Quando roda**: Após training

#### 6️⃣ **Deploy to Azure**
- ☁️ Upload de modelos para Azure Blob Storage
- 🚀 Deploy de endpoint (opcional)

**Quando roda**: **Somente** no branch `main` com `push`

#### 7️⃣ **Notify**
- 📱 Envia notificação via Telegram
- ✅ Sucesso ou ❌ Falha

**Quando roda**: Sempre ao final

---

## Como Usar

### Opção 1: Push Automático

**Trigger em push para branches específicos**:

```bash
# Branch dev - roda validação + feature engineering + train
git checkout dev
git commit -m "feat: add new feature"
git push

# Branch staging - mesma coisa
git checkout staging
git push

# Branch main - roda TUDO incluindo deploy
git checkout main
git merge staging
git push  # ← Vai fazer deploy na Azure!
```

### Opção 2: Workflow Manual (Recomendado para testes)

1. Vá em **Actions** → **Azure ML Pipeline**
2. Clique em **Run workflow**
3. Selecione:
   - **Branch**: `dev`, `staging`, ou `main`
   - **Config file**: `configs/btcusdt_1m_dev.jsonc`
   - **Pipeline mode**: `quick`, `full`, ou `train-only`

**Modos de Pipeline**:

- **`quick`** (5-10 min):
  - Feature engineering com dados existentes
  - Train rápido
  - Validação básica

- **`full`** (30-60 min):
  - Download completo de dados
  - Feature engineering completo
  - Train completo
  - Validação extensa

- **`train-only`** (10-20 min):
  - Pula download e features
  - Apenas treina modelos
  - Útil para testar hiperparâmetros

### Opção 3: Forçar Download

Se você quer forçar re-download de dados mesmo em push:

```bash
git commit -m "refactor: improve strategy [download]"
#                                        ^^^^^^^^^^
#                                        Trigger keyword
git push
```

---

## Visualizando Resultados

### Artifacts

Após cada execução, você pode baixar:

1. **raw-data**: Dados baixados da Binance (7 dias)
2. **features-and-labels**: Features e labels gerados (7 dias)
3. **trained-models**: Modelos treinados (30 dias)
4. **training-metrics**: Métricas de performance (30 dias)

**Como baixar**:
1. Vá em **Actions** → Selecione a execução
2. Scroll até **Artifacts**
3. Clique para download

### Logs

Clique em cada job para ver logs detalhados:

```
Validate Code & Dependencies
  ✓ Checkout code
  ✓ Set up Python 3.10
  ✓ Install dependencies
  ✓ Validate Python syntax
  ...
```

### Métricas de Training

O arquivo `prediction-metrics.txt` contém:

```
Model: lgbm_high_20
Accuracy: 0.8234
Precision: 0.7845
Recall: 0.8123
F1-Score: 0.7982
...
```

---

## Configurações Avançadas

### Configurar Schedule (Cron)

Para executar automaticamente todos os dias às 2h UTC:

```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC diariamente
  push:
    branches:
      - main
  # ...
```

### Configurar Environments

Para proteger deploy em produção:

1. Vá em **Settings** → **Environments**
2. Crie `production`
3. Configure **Required reviewers** (opcional)
4. Configure **Deployment branches** → `main` only

### Usar Azure ML Workspace (Avançado)

Se quiser usar Azure ML para treinar:

```yaml
- name: Train on Azure ML
  run: |
    az ml job create \
      --file azure-ml-job.yml \
      --resource-group rg-trading-bot \
      --workspace-name ws-trading-bot
```

---

## Troubleshooting

### Erro: "Azure credentials not found"

**Solução**: Verificar se o secret `AZURE_CREDENTIALS` está configurado corretamente.

```bash
# Testar localmente
az login --service-principal \
  --username $CLIENT_ID \
  --password $CLIENT_SECRET \
  --tenant $TENANT_ID
```

### Erro: "Binance API rate limit"

**Solução**: Reduzir frequência de downloads ou usar dados cached.

```yaml
# Mudar de 'full' para 'quick'
pipeline_mode: quick
```

### Erro: "Model training failed - memory"

**Solução**: Usar runner com mais memória ou reduzir tamanho dos dados.

```yaml
runs-on: ubuntu-latest-4-cores  # Mais RAM
```

Ou no config:

```jsonc
{
  "train_length": 100000,  // Reduzir de 525600
  // ...
}
```

### Erro: "Artifact upload failed"

**Solução**: Verificar tamanho dos arquivos (max 500MB por artifact).

```bash
# Comprimir antes de upload
- name: Compress models
  run: tar -czf models.tar.gz MODELS_*

- name: Upload
  uses: actions/upload-artifact@v4
  with:
    name: models-compressed
    path: models.tar.gz
```

### Workflow não roda no push

**Causas comuns**:
1. Branch não está na lista (`main`, `staging`, `dev`)
2. Workflow YAML tem erro de sintaxe
3. Sem permissões de Actions (Settings → Actions → General)

**Solução**:
```bash
# Validar YAML localmente
pip install yamllint
yamllint .github/workflows/azure-pipeline.yml
```

---

## Monitoramento

### Telegram Notifications

Você receberá notificações:

✅ **Sucesso**:
```
✅ Pipeline completed successfully!

Commit: abc1234
Branch: main
Workflow: Azure ML Pipeline
```

❌ **Falha**:
```
❌ Pipeline failed!

Commit: abc1234
Branch: staging
Check: [Link para logs]
```

### Métricas de Custos

Para monitorar custos da Azure:

```bash
# Ver custos atuais
az consumption usage list \
  --start-date 2025-12-01 \
  --end-date 2025-12-11 \
  --output table

# Ou use o script
python scripts/cloud_cost_monitor.py
```

---

## Checklist de Setup Inicial

Use este checklist antes de ativar o workflow:

- [ ] Azure Service Principal criado
- [ ] Azure Storage Account criado
- [ ] Container `models` existe
- [ ] Secret `AZURE_CREDENTIALS` configurado
- [ ] Secret `AZURE_STORAGE_ACCOUNT` configurado
- [ ] Secret `BINANCE_API_KEY` configurado
- [ ] Secret `BINANCE_API_SECRET` configurado
- [ ] Secret `TELEGRAM_BOT_TOKEN` configurado
- [ ] Secret `TELEGRAM_CHAT_ID` configurado
- [ ] Workflow testado localmente (`./test_pipeline_local.sh`)
- [ ] Config file validado ([configs/btcusdt_1m_dev.jsonc](configs/btcusdt_1m_dev.jsonc))
- [ ] `.env.sample` copiado para `.env` localmente

---

## Próximos Passos

Depois do setup:

1. ✅ Testar workflow manualmente (Actions → Run workflow → `quick`)
2. ✅ Verificar artifacts e logs
3. ✅ Fazer um push no `dev` para testar trigger automático
4. ✅ Se tudo OK, merge para `staging`
5. ✅ Se staging OK, merge para `main` → deploy automático!

---

## Recursos

- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [Azure CLI Reference](https://learn.microsoft.com/en-us/cli/azure/)
- [Azure Storage Docs](https://learn.microsoft.com/en-us/azure/storage/)
- [Binance API Docs](https://binance-docs.github.io/apidocs/)

---

**Última atualização**: 2025-12-11
**Versão**: 1.0
