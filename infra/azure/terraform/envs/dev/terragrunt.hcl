# -----------------------------------------------------------------------------
# Azure Dev Environment - Terragrunt Configuration
# -----------------------------------------------------------------------------

include "root" {
  path = find_in_parent_folders()
}

include "azure" {
  path = find_in_parent_folders("azure/terragrunt.hcl")
}

# Use the terraform code in current directory
terraform {
  source = "."
}

# Environment-specific inputs
inputs = {
  project_name = "itb-dev"
  environment  = "dev"

  # Secrets loaded from environment variables
  # Export: TF_VAR_binance_api_key, TF_VAR_binance_api_secret
}
