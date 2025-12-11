# -----------------------------------------------------------------------------
# GCP Project
# -----------------------------------------------------------------------------

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "us-central1-a"
}

# -----------------------------------------------------------------------------
# Naming
# -----------------------------------------------------------------------------

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "itb"
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
