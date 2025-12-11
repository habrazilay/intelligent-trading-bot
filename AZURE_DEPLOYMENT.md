# 🚀 Azure Container Instances - Shadow Mode Deployment

This guide shows how to deploy the trading bot to **Azure Container Instances** for running shadow mode 24/7.

---

## 📋 Prerequisites

### 1. GitHub Variables Configured
Set these in **Settings** → **Secrets and variables** → **Actions** → **Variables**:

```
ACR_LOGIN_SERVER=itbacr.azurecr.io
ACR_REPOSITORY=itb-bot
AZURE_RESOURCE_GROUP=rg-itb-dev
AZURE_REGION=eastus
AZURE_CONTAINER_PREFIX=itb-bot
AZURE_STORAGE_ACCOUNT=stitbdev
```

### 2. GitHub Secrets Configured
See `GITHUB_SETUP.md` for the full list.

---

## 🏗️ Azure Resources Setup

### 1. Create Azure Container Registry (ACR)

```bash
az acr create \
  --resource-group rg-itb-dev \
  --name itbacr \
  --sku Basic \
  --location eastus
```

### 2. Verify Azure Storage Account

Your data is in the **stitbdev** storage account. Check the file shares:

```bash
az storage share list \
  --account-name stitbdev \
  --output table
```

You should see:
- `data-itb-1m` (if using 1-minute data)
- `data-itb-5m` (if using 5-minute data)
- `data-itb-1h` (if using 1-hour data)

### 3. Get Storage Account Key

```bash
STORAGE_KEY=$(az storage account keys list \
  --resource-group rg-itb-dev \
  --account-name stitbdev \
  --query '[0].value' \
  --output tsv)

echo $STORAGE_KEY
```

Add this as a GitHub Secret: `AZURE_STORAGE_KEY`

---

## 🐳 Deploy Container to Azure

### Option 1: Manual Deployment (Azure CLI)

```bash
az container create \
  --resource-group rg-itb-dev \
  --name itb-bot-shadow-5m \
  --image ${{ vars.ACR_LOGIN_SERVER }}/itb-bot:minimal \
  --registry-login-server ${{ vars.ACR_LOGIN_SERVER }} \
  --registry-username ${{ secrets.ACR_USERNAME }} \
  --registry-password ${{ secrets.ACR_PASSWORD }} \
  --cpu 1 \
  --memory 2 \
  --restart-policy Always \
  --environment-variables \
    PYTHONUNBUFFERED=1 \
    BINANCE_API_KEY=${{ secrets.BINANCE_API_KEY }} \
    BINANCE_API_SECRET=${{ secrets.BINANCE_API_SECRET }} \
    BINANCE_USE_TESTNET=true \
    TELEGRAM_BOT_TOKEN=${{ secrets.TELEGRAM_BOT_TOKEN }} \
    TELEGRAM_CHAT_ID=${{ secrets.TELEGRAM_CHAT_ID }} \
  --azure-file-volume-account-name stitbdev \
  --azure-file-volume-account-key $STORAGE_KEY \
  --azure-file-volume-share-name data-itb-5m \
  --azure-file-volume-mount-path /app/DATA_ITB_5m \
  --command-line "python -m scripts.output -c configs/base_conservative.jsonc --symbol BTCUSDT --freq 5m"
```

### Option 2: Add to GitHub Actions Workflow

Add this job to `.github/workflows/azure-pipeline.yml`:

```yaml
  deploy-container-instance:
    name: Deploy to Azure Container Instance
    runs-on: ubuntu-latest
    needs: [build-docker, backtest]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'

    steps:
      - name: Login to Azure
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Set defaults
        id: set-defaults
        run: |
          SYMBOL="${{ github.event.inputs.symbol || 'BTCUSDT' }}"
          FREQ="${{ github.event.inputs.freq || '5m' }}"
          STRATEGY="${{ github.event.inputs.strategy || 'conservative' }}"

          echo "symbol=$SYMBOL" >> $GITHUB_OUTPUT
          echo "freq=$FREQ" >> $GITHUB_OUTPUT
          echo "strategy=$STRATEGY" >> $GITHUB_OUTPUT
          echo "container_name=${{ vars.AZURE_CONTAINER_PREFIX }}-$FREQ" >> $GITHUB_OUTPUT
          echo "file_share=data-itb-$FREQ" >> $GITHUB_OUTPUT
          echo "data_path=/app/DATA_ITB_$FREQ" >> $GITHUB_OUTPUT

      - name: Stop existing container
        continue-on-error: true
        run: |
          az container delete \
            --resource-group ${{ vars.AZURE_RESOURCE_GROUP }} \
            --name ${{ steps.set-defaults.outputs.container_name }} \
            --yes

      - name: Deploy new container
        run: |
          az container create \
            --resource-group ${{ vars.AZURE_RESOURCE_GROUP }} \
            --name ${{ steps.set-defaults.outputs.container_name }} \
            --image ${{ secrets.DOCKER_USERNAME }}/intelligent-trading-bot:minimal \
            --cpu 1 \
            --memory 2 \
            --restart-policy Always \
            --environment-variables \
              PYTHONUNBUFFERED=1 \
              BINANCE_USE_TESTNET=true \
            --secure-environment-variables \
              BINANCE_API_KEY=${{ secrets.BINANCE_API_KEY }} \
              BINANCE_API_SECRET=${{ secrets.BINANCE_API_SECRET }} \
              TELEGRAM_BOT_TOKEN=${{ secrets.TELEGRAM_BOT_TOKEN }} \
              TELEGRAM_CHAT_ID=${{ secrets.TELEGRAM_CHAT_ID }} \
            --azure-file-volume-account-name ${{ secrets.AZURE_STORAGE_ACCOUNT }} \
            --azure-file-volume-account-key ${{ secrets.AZURE_STORAGE_KEY }} \
            --azure-file-volume-share-name ${{ steps.set-defaults.outputs.file_share }} \
            --azure-file-volume-mount-path ${{ steps.set-defaults.outputs.data_path }} \
            --command-line "python -m scripts.output -c configs/base_${{ steps.set-defaults.outputs.strategy }}.jsonc --symbol ${{ steps.set-defaults.outputs.symbol }} --freq ${{ steps.set-defaults.outputs.freq }}"

      - name: Get container status
        run: |
          az container show \
            --resource-group ${{ vars.AZURE_RESOURCE_GROUP }} \
            --name ${{ steps.set-defaults.outputs.container_name }} \
            --query '{Name:name,Status:containers[0].instanceView.currentState.state,IP:ipAddress.ip}' \
            --output table

      - name: Create deployment summary
        run: |
          echo "## Container Instance Deployed" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "✅ Container: ${{ steps.set-defaults.outputs.container_name }}" >> $GITHUB_STEP_SUMMARY
          echo "📊 Symbol: ${{ steps.set-defaults.outputs.symbol }}" >> $GITHUB_STEP_SUMMARY
          echo "⏱️ Frequency: ${{ steps.set-defaults.outputs.freq }}" >> $GITHUB_STEP_SUMMARY
          echo "📈 Strategy: ${{ steps.set-defaults.outputs.strategy }}" >> $GITHUB_STEP_SUMMARY
          echo "💾 Data: ${{ steps.set-defaults.outputs.file_share }} → ${{ steps.set-defaults.outputs.data_path }}" >> $GITHUB_STEP_SUMMARY
```

---

## 📊 Monitoring

### View Container Logs
```bash
az container logs \
  --resource-group rg-itb-dev \
  --name itb-bot-shadow-5m \
  --follow
```

### Check Container Status
```bash
az container show \
  --resource-group rg-itb-dev \
  --name itb-bot-shadow-5m \
  --query 'containers[0].instanceView.currentState' \
  --output table
```

### Stop Container
```bash
az container stop \
  --resource-group rg-itb-dev \
  --name itb-bot-shadow-5m
```

### Delete Container
```bash
az container delete \
  --resource-group rg-itb-dev \
  --name itb-bot-shadow-5m \
  --yes
```

---

## 🔄 Data Flow

```
1. GitHub Actions builds minimal Docker image
2. Pushes to Docker Hub (or ACR)
3. Azure Container Instance pulls image
4. Mounts Azure File Share (stitbdev/data-itb-5m → /app/DATA_ITB_5m)
5. Runs: python -m scripts.output -c configs/base_conservative.jsonc --symbol BTCUSDT --freq 5m
6. Bot reads models and data from mounted volume
7. Generates predictions and executes trades (shadow mode)
8. Sends Telegram notifications
```

---

## 💰 Cost Estimation

**Azure Container Instances** pricing (East US):

- CPU: 1 vCPU × $0.0000125/second = ~$32.40/month
- Memory: 2 GB × $0.0000014/second = ~$3.63/month
- **Total: ~$36/month per container**

**Azure Storage** (stitbdev):
- File Share: ~$0.06/GB/month
- For 10 GB of historical data: ~$0.60/month

**Total estimated cost: ~$37/month**

---

## 🚨 Production Checklist

Before deploying to production:

- [ ] Set `BINANCE_USE_TESTNET=false` (currently true)
- [ ] Verify backtesting results are profitable
- [ ] Start with small position sizes
- [ ] Monitor Telegram notifications for 24 hours
- [ ] Check Azure container logs daily
- [ ] Set up Azure Monitor alerts
- [ ] Configure auto-restart policy
- [ ] Test fail-over scenarios

---

## 🔗 Related Files

- `Dockerfile` - Multi-stage build (production target)
- `DOCKER_GUIDE.md` - Docker build and run guide
- `GITHUB_SETUP.md` - GitHub secrets/variables setup
- `.github/workflows/azure-pipeline.yml` - CI/CD pipeline
