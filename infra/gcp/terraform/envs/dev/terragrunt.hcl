# -----------------------------------------------------------------------------
# GCP Dev Environment - Terragrunt Configuration
# -----------------------------------------------------------------------------

include "root" {
  path = find_in_parent_folders()
}

include "gcp" {
  path = find_in_parent_folders("gcp/terragrunt.hcl")
}

# Use the terraform code in current directory
terraform {
  source = "."
}

# Environment-specific inputs
inputs = {
  environment = "dev"

  # Project ID loaded from environment variable
  # Export: TF_VAR_project_id

  # Secrets loaded from environment variables
  # Export: TF_VAR_binance_api_key, TF_VAR_binance_api_secret
}
