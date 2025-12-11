# -----------------------------------------------------------------------------
# Resource Group
# -----------------------------------------------------------------------------

output "resource_group_name" {
  value = azurerm_resource_group.rg.name
}

# -----------------------------------------------------------------------------
# Storage
# -----------------------------------------------------------------------------

output "storage_account_name" {
  value = azurerm_storage_account.sa.name
}

output "file_share_name_1m" {
  value = azurerm_storage_share.share.name
}

output "file_share_name_5m" {
  value = azurerm_storage_share.share_5m.name
}

output "file_share_name_1h" {
  value = azurerm_storage_share.share_1h.name
}

# -----------------------------------------------------------------------------
# Key Vault
# -----------------------------------------------------------------------------

output "key_vault_name" {
  value = azurerm_key_vault.kv.name
}

output "key_vault_uri" {
  value = azurerm_key_vault.kv.vault_uri
}

output "key_vault_id" {
  value     = azurerm_key_vault.kv.id
  sensitive = true
}

# -----------------------------------------------------------------------------
# Azure Machine Learning
# -----------------------------------------------------------------------------

output "ml_workspace_name" {
  description = "Azure ML Workspace name"
  value       = azurerm_machine_learning_workspace.ml.name
}

output "ml_workspace_id" {
  description = "Azure ML Workspace ID"
  value       = azurerm_machine_learning_workspace.ml.id
}

output "ml_workspace_discovery_url" {
  description = "Azure ML Workspace discovery URL"
  value       = azurerm_machine_learning_workspace.ml.discovery_url
}

output "mlflow_tracking_uri" {
  description = "MLflow tracking URI for the workspace"
  value       = "azureml://${azurerm_resource_group.rg.location}.api.azureml.ms/mlflow/v1.0/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/${azurerm_resource_group.rg.name}/providers/Microsoft.MachineLearningServices/workspaces/${azurerm_machine_learning_workspace.ml.name}"
}

# Compute cluster disabled until vCPU quota is available
# output "ml_compute_cluster_name" {
#   description = "Azure ML compute cluster name"
#   value       = azurerm_machine_learning_compute_cluster.training.name
# }
