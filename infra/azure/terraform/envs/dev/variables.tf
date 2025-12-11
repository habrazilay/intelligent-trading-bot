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
