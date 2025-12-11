# -----------------------------------------------------------------------------
# Azure-specific Terragrunt Configuration
# Inherited by all Azure environments
# -----------------------------------------------------------------------------

include "root" {
  path = find_in_parent_folders()
}

# Azure-specific inputs
inputs = {
  location = "eastus"
}
