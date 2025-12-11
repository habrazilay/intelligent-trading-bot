# -----------------------------------------------------------------------------
# Azure Key Vault - Secrets Management
# -----------------------------------------------------------------------------

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "kv" {
  name                = "kv-${replace(var.project_name, "-", "")}01"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Security settings
  enabled_for_deployment          = false
  enabled_for_disk_encryption     = false
  enabled_for_template_deployment = false
  purge_protection_enabled        = false  # Set true in production
  soft_delete_retention_days      = 7

  # Network rules (allow all for dev, restrict in prod)
  network_acls {
    default_action = "Allow"
    bypass         = "AzureServices"
  }

  tags = {
    environment = "dev"
    project     = var.project_name
    managed_by  = "terraform"
  }
}

# Access policy for current user/service principal
resource "azurerm_key_vault_access_policy" "current" {
  key_vault_id = azurerm_key_vault.kv.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = [
    "Get",
    "List",
    "Set",
    "Delete",
    "Purge",
    "Recover"
  ]
}

# -----------------------------------------------------------------------------
# Secrets - Binance API
# -----------------------------------------------------------------------------

resource "azurerm_key_vault_secret" "binance_api_key" {
  name         = "binance-api-key"
  value        = var.binance_api_key
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [azurerm_key_vault_access_policy.current]

  tags = {
    purpose = "binance-trading"
  }
}

resource "azurerm_key_vault_secret" "binance_api_secret" {
  name         = "binance-api-secret"
  value        = var.binance_api_secret
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [azurerm_key_vault_access_policy.current]

  tags = {
    purpose = "binance-trading"
  }
}

# -----------------------------------------------------------------------------
# Secrets - Telegram (optional)
# -----------------------------------------------------------------------------

resource "azurerm_key_vault_secret" "telegram_bot_token" {
  count        = var.telegram_bot_token != "" ? 1 : 0
  name         = "telegram-bot-token"
  value        = var.telegram_bot_token
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [azurerm_key_vault_access_policy.current]
}

resource "azurerm_key_vault_secret" "telegram_chat_id" {
  count        = var.telegram_chat_id != "" ? 1 : 0
  name         = "telegram-chat-id"
  value        = var.telegram_chat_id
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [azurerm_key_vault_access_policy.current]
}
