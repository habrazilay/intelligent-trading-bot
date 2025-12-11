# -----------------------------------------------------------------------------
# General
# -----------------------------------------------------------------------------

variable "project_name" {
  description = "Logical name for this environment (used as suffix/prefix in resource names)"
  type        = string
  default     = "itb-dev"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

# -----------------------------------------------------------------------------
# Secrets - Binance
# -----------------------------------------------------------------------------

variable "binance_api_key" {
  description = "Binance API Key"
  type        = string
  sensitive   = true
}

variable "binance_api_secret" {
  description = "Binance API Secret"
  type        = string
  sensitive   = true
}

# -----------------------------------------------------------------------------
# Secrets - Telegram (optional)
# -----------------------------------------------------------------------------

variable "telegram_bot_token" {
  description = "Telegram Bot Token (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "telegram_chat_id" {
  description = "Telegram Chat ID (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

# -----------------------------------------------------------------------------
# Azure Machine Learning
# -----------------------------------------------------------------------------

variable "ml_compute_cluster_name" {
  description = "Name of the Azure ML compute cluster"
  type        = string
  default     = "itb-training"
}

variable "ml_compute_vm_size" {
  description = "VM size for the compute cluster"
  type        = string
  default     = "Standard_DS3_v2"
}

variable "ml_compute_vm_priority" {
  description = "VM priority (Dedicated or LowPriority)"
  type        = string
  default     = "LowPriority"
}

variable "ml_compute_min_nodes" {
  description = "Minimum number of nodes (0 = scale to zero)"
  type        = number
  default     = 0
}

variable "ml_compute_max_nodes" {
  description = "Maximum number of nodes"
  type        = number
  default     = 4
}

variable "ml_scale_down_minutes" {
  description = "Minutes of idle time before scaling down"
  type        = number
  default     = 15
}

# -----------------------------------------------------------------------------
# Data Collector VM
# -----------------------------------------------------------------------------

variable "collector_vm_size" {
  description = "VM size for the data collector (B1s is cheapest ~$15/month)"
  type        = string
  default     = "Standard_B1s"
}

variable "ssh_public_key" {
  description = "SSH public key for VM access"
  type        = string
  default     = ""
}
