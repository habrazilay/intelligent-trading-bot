resource "azurerm_kubernetes_cluster" "this" {
  name                = "${var.prefix}-aks"
  location            = var.location
  resource_group_name = var.rg_name
  dns_prefix          = "${var.prefix}-dns"

  kubernetes_version  = "1.30"

  # Control‑plane
  sku_tier = var.sku_tier          # "Free" ou "Standard"

  default_node_pool {
    name       = "default"
    node_count = var.node_count
    vm_size    = var.vm_size
    os_disk_size_gb = 30
    max_pods   = 30
  }

  dynamic "linux_profile" {
    for_each = var.admin_username == null ? [] : [1]
    content {
      admin_username = var.admin_username
      ssh_key {
        key_data = var.ssh_public_key
      }
    }
  }

  # Add‑ons nativos
  key_vault_secrets_provider { enabled = true }
  azure_policy_enabled       = true
  oms_agent                  { log_analytics_workspace_id = var.law_id }
  workload_identity_enabled  = true
  oidc_issuer_enabled        = true

  identity {
    type = "SystemAssigned"
  }

  tags = merge(local.default_tags, var.tags)
}

# Node pool opcional Spot
resource "azurerm_kubernetes_cluster_node_pool" "spot" {
  count       = var.spot_enabled ? 1 : 0
  name        = "spot"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size     = var.vm_size
  node_count  = var.spot_count
  max_pods    = 30
  priority    = "Spot"
  eviction_policy = "Delete"
  spot_max_price  = -1          # preço flutuante no limite do on‑demand
  tags        = merge(local.default_tags, { pool = "spot" })
}