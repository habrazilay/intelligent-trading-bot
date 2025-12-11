# 🔐 GitHub Variables & Secrets Setup

This document lists all the **Variables** and **Secrets** you need to configure in your GitHub repository for the CI/CD pipeline to work.

---

## 📍 Where to Configure

Go to: **Settings** → **Secrets and variables** → **Actions**

- **Secrets** (🔒): Sensitive data like API keys, passwords
- **Variables** (📝): Configuration values like resource names

---

## 🔑 Required Secrets

### Docker Hub (for building and pushing images)
| Secret Name | Example Value | Description |
|-------------|---------------|-------------|
| `DOCKER_USERNAME` | `yourname` | Your Docker Hub username |
| `DOCKER_PASSWORD` | `dckr_pat_xxx` | Docker Hub access token |

### Binance API (for downloading trading data)
| Secret Name | Example Value | Description |
|-------------|---------------|-------------|
| `BINANCE_API_KEY` | `xxxxxxxxxxxxx` | Binance API key |
| `BINANCE_API_SECRET` | `xxxxxxxxxxxxx` | Binance API secret |

### Azure (for deployment and storage)
| Secret Name | Example Value | Description |
|-------------|---------------|-------------|
| `AZURE_CREDENTIALS` | `{"clientId":"..."}` | Azure service principal JSON |
| `AZURE_STORAGE_ACCOUNT` | `stitbdev` | Azure Storage Account name |

### Telegram (for notifications)
| Secret Name | Example Value | Description |
|-------------|---------------|-------------|
| `TELEGRAM_BOT_TOKEN` | `123456:ABC-DEF...` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | `-1001234567890` | Your chat/group ID |

---

## 📝 Required Variables (Optional - for Azure Container Instances)

If you plan to deploy to **Azure Container Instances**, configure these variables:

| Variable Name | Example Value | Description |
|---------------|---------------|-------------|
| `ACR_LOGIN_SERVER` | `itbacr.azurecr.io` | Azure Container Registry URL |
| `ACR_REPOSITORY` | `itb-bot` | Repository name in ACR |
| `AZURE_RESOURCE_GROUP` | `rg-itb-dev` | Azure resource group |
| `AZURE_REGION` | `eastus` | Azure deployment region |
| `AZURE_CONTAINER_PREFIX` | `itb-bot` | Prefix for container instances |

---

## 🔧 How to Get Azure Credentials

### 1. Create Service Principal

```bash
az ad sp create-for-rbac \
  --name "github-actions-itb" \
  --role contributor \
  --scopes /subscriptions/{subscription-id}/resourceGroups/rg-itb-dev \
  --sdk-auth
```

### 2. Copy the JSON output to `AZURE_CREDENTIALS` secret

```json
{
  "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "clientSecret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "subscriptionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  "activeDirectoryGraphResourceId": "https://graph.windows.net/",
  "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
  "galleryEndpointUrl": "https://gallery.azure.com/",
  "managementEndpointUrl": "https://management.core.windows.net/"
}
```

---

## 📋 Current Workflow Usage

The `azure-pipeline.yml` currently uses these secrets:

### Docker Build Job
```yaml
username: ${{ secrets.DOCKER_USERNAME }}
password: ${{ secrets.DOCKER_PASSWORD }}
```

### Download Data Job
```yaml
BINANCE_API_KEY: ${{ secrets.BINANCE_API_KEY }}
BINANCE_API_SECRET: ${{ secrets.BINANCE_API_SECRET }}
```

### Deploy to Azure Job
```yaml
creds: ${{ secrets.AZURE_CREDENTIALS }}
--account-name ${{ secrets.AZURE_STORAGE_ACCOUNT }}
```

### Telegram Notifications
```yaml
TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```

---

## ✅ Verification Checklist

After configuring secrets, verify they're set:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Check that all required secrets appear in the list (values hidden)
3. Run a test workflow with `workflow_dispatch` to validate

---

## 🚨 Security Best Practices

1. **NEVER** commit secrets to the repository
2. **NEVER** use secrets in workflow names or outputs
3. **USE** `BINANCE_USE_TESTNET=true` for initial testing
4. **ROTATE** API keys regularly
5. **LIMIT** Azure service principal permissions to specific resource groups

---

## 🔗 Related Files

- `.github/workflows/azure-pipeline.yml` - Main CI/CD pipeline
- `Dockerfile` - Multi-stage Docker build
- `DOCKER_GUIDE.md` - Docker usage guide
