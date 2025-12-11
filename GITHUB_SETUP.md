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
| `DOCKERHUB_USER` | `yourname` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | `dckr_pat_xxx` | Docker Hub access token |

### Azure Container Registry (ACR) - Optional
| Secret Name | Example Value | Description |
|-------------|---------------|-------------|
| `ACR_USERNAME` | `itbacr` | Azure Container Registry username |
| `ACR_PASSWORD` | `xxx...` | Azure Container Registry password |

### Binance API (for downloading trading data)
| Secret Name | Example Value | Description |
|-------------|---------------|-------------|
| `BINANCE_API_KEY` | `xxxxxxxxxxxxx` | Binance API key |
| `BINANCE_API_SECRET` | `xxxxxxxxxxxxx` | Binance API secret |

### Azure (for deployment and storage)
| Secret Name | Example Value | Description |
|-------------|---------------|-------------|
| `AZURE_CREDENTIALS` | `{"clientId":"..."}` | Azure service principal JSON |
| `AZURE_STORAGE_KEY` | `xxx...` | Azure Storage Account key |

### Telegram (for notifications)
| Secret Name | Example Value | Description |
|-------------|---------------|-------------|
| `TELEGRAM_BOT_TOKEN` | `123456:ABC-DEF...` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | `-1001234567890` | Your chat/group ID |

---

## 📝 Required Variables (for Azure Container Instances)

Configure these variables in **Environment: env** (Settings → Environments → env → Environment variables):

| Variable Name | Description |
|---------------|-------------|
| `ACR_LOGIN_SERVER` | Azure Container Registry URL |
| `ACR_REPOSITORY` | Repository name in ACR |
| `AZURE_RESOURCE_GROUP` | Azure resource group |
| `AZURE_FILE_SHARE_1M` | File share name for 1-minute data |
| `AZURE_FILE_SHARE_5M` | File share name for 5-minute data |
| `AZURE_FILE_SHARE_1H` | File share name for 1-hour data |
| `AZURE_STORAGE_ACCOUNT` | Azure Storage Account name |

✅ **Already configured in your "env" environment!**

### Using Environment Variables in Workflows

To use these environment variables in GitHub Actions, add the `environment` key to your job:

```yaml
deploy-azure:
  name: Deploy to Azure
  runs-on: ubuntu-latest
  environment: env  # This loads all variables from the "env" environment

  steps:
    - name: Example step
      run: |
        echo "Using ACR: ${{ vars.ACR_LOGIN_SERVER }}"
        echo "Resource Group: ${{ vars.AZURE_RESOURCE_GROUP }}"
```

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

## 📋 Workflow Usage

To use environment variables in your workflow, add `environment: env` to jobs that need Azure deployment:

```yaml
deploy-container-instance:
  name: Deploy to Azure Container Instance
  runs-on: ubuntu-latest
  environment: env  # This is required to access env variables!

  steps:
    - name: Deploy container
      run: |
        az container create \
          --resource-group ${{ vars.AZURE_RESOURCE_GROUP }} \
          --image ${{ vars.ACR_LOGIN_SERVER }}/${{ vars.ACR_REPOSITORY }}:minimal \
          --azure-file-volume-account-name ${{ vars.AZURE_STORAGE_ACCOUNT }} \
          --azure-file-volume-share-name ${{ vars.AZURE_FILE_SHARE_5M }}
```

### Secrets Usage (no environment needed)

Repository secrets can be used in any job without specifying environment:

```yaml
- name: Login to Docker Hub
  uses: docker/login-action@v3
  with:
    username: ${{ secrets.DOCKERHUB_USER }}
    password: ${{ secrets.DOCKERHUB_TOKEN }}
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
