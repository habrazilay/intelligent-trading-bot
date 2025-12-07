module "resource_group" {
  source  = "Azure/resource-group/azurerm"
  version = "2.0.0"

  name     = "rg-itb-dev"
  location = var.location
  tags     = local.default_tags
}

module "log_analytics" {
  source  = "Azure/monitor/azurerm"
  version = "0.9.1"

  location            = var.location
  resource_group_name = module.resource_group.name
  workspace_name      = "law-itb-dev"
}

module "keyvault" {
  source              = "../../modules/keyvault"
  rg_name             = module.resource_group.name
  location            = var.location
  prefix              = "itb-dev"
  law_id              = module.log_analytics.workspace_id
}

module "acr" {
  source              = "../../modules/acr"
  rg_name             = module.resource_group.name
  location            = var.location
  prefix              = "itbdev"
}

module "aks" {
  source              = "../../modules/aks"
  prefix              = "itb-dev"
  rg_name             = module.resource_group.name
  location            = var.location
  sku_tier            = "Free"
  node_count          = 1
  spot_enabled        = true
  spot_count          = 2
  vm_size             = "Standard_D2as_v5"
  law_id              = module.log_analytics.workspace_id
  tags                = { environment = "dev" }
}

module "postgres" {
  source              = "../../modules/postgresql"
  rg_name             = module.resource_group.name
  vnet_id             = module.aks.vnet_id
  subnet_id           = module.aks.db_subnet_id
  # …
}

module "redis" { /* similar */ }

output "kubeconfig" {
  value = module.aks.kubeconfig
  sensitive = true
}