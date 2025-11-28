resource "azurerm_resource_group" "rg" {
  name     = "rg-${var.project_name}"
  location = var.location
}

resource "azurerm_storage_account" "sa" {
  name                     = "st${replace(var.project_name, "-", "")}"  # precisa ser único e minúsculo
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  # Opcional: mais configurações (https only, etc.)
  min_tls_version          = "TLS1_2"
}

resource "azurerm_storage_share" "share" {
  name                 = "data-itb-1m"
  storage_account_name = azurerm_storage_account.sa.name
  quota                = 50  # GB
}