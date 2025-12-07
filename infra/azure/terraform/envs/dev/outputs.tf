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
