terraform {
  backend "azurerm" {
    resource_group_name  = "tfstate-rg"
    storage_account_name = "tfstateitb"
    container_name       = "state"
    key                  = "dev.tfstate"
  }
}