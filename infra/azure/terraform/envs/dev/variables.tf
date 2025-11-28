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