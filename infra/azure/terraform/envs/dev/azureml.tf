# -----------------------------------------------------------------------------
# Azure Machine Learning Workspace
# -----------------------------------------------------------------------------

resource "azurerm_application_insights" "ml" {
  name                = "appi-${var.project_name}-ml"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  application_type    = "web"

  tags = {
    environment = "dev"
    project     = var.project_name
    managed_by  = "terraform"
  }
}

resource "azurerm_machine_learning_workspace" "ml" {
  name                          = "mlw-${var.project_name}"
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  application_insights_id       = azurerm_application_insights.ml.id
  key_vault_id                  = azurerm_key_vault.kv.id
  storage_account_id            = azurerm_storage_account.sa.id
  public_network_access_enabled = true

  identity {
    type = "SystemAssigned"
  }

  tags = {
    environment = "dev"
    project     = var.project_name
    managed_by  = "terraform"
  }
}

# -----------------------------------------------------------------------------
# Azure ML Compute Cluster for Training
# NOTE: Requires vCPU quota. Request quota increase at:
# https://portal.azure.com/#blade/Microsoft_Azure_Capacity/UsageAndQuota.ReactView
# -----------------------------------------------------------------------------

# Commented out until vCPU quota is available
# resource "azurerm_machine_learning_compute_cluster" "training" {
#   name                          = var.ml_compute_cluster_name
#   machine_learning_workspace_id = azurerm_machine_learning_workspace.ml.id
#   location                      = azurerm_resource_group.rg.location
#   vm_priority                   = var.ml_compute_vm_priority
#   vm_size                       = var.ml_compute_vm_size
#
#   scale_settings {
#     min_node_count                       = var.ml_compute_min_nodes
#     max_node_count                       = var.ml_compute_max_nodes
#     scale_down_nodes_after_idle_duration = "PT${var.ml_scale_down_minutes}M"
#   }
#
#   identity {
#     type = "SystemAssigned"
#   }
#
#   tags = {
#     environment = "dev"
#     project     = var.project_name
#     managed_by  = "terraform"
#   }
# }

# -----------------------------------------------------------------------------
# NOTE: Datastores can be created via Azure ML Studio or CLI after workspace
# is provisioned. The terraform provider has issues with fileshare IDs.
#
# Create via CLI:
# az ml datastore create --name datastore_itb_1m --type azure_file \
#   --workspace-name mlw-itb-dev --resource-group rg-itb-dev \
#   --account-name stitbdev --file-share-name data-itb-1m
# -----------------------------------------------------------------------------
