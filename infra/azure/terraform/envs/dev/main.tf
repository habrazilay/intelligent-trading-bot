resource "azurerm_resource_group" "rg" {
  name     = "rg-${var.project_name}"
  location = var.location
}

resource "azurerm_container_registry" "acr" {
  name                = "itbacr"  # usa o mesmo nome do ACR existente
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
  admin_enabled       = true
}

resource "azurerm_storage_account" "sa" {
  name                     = "stitbdev"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_share" "share" {    # 1m - já existe
  name               = "data-itb-1m"
  storage_account_id = azurerm_storage_account.sa.id
  quota              = 100
}

resource "azurerm_storage_share" "share_5m" { # novo
  name               = "data-itb-5m"
  storage_account_id = azurerm_storage_account.sa.id
  quota              = 100
}

resource "azurerm_storage_share" "share_1h" { # novo
  name               = "data-itb-1h"
  storage_account_id = azurerm_storage_account.sa.id
  quota              = 100
}
