# -----------------------------------------------------------------------------
# GCP-specific Terragrunt Configuration
# Inherited by all GCP environments
# -----------------------------------------------------------------------------

include "root" {
  path = find_in_parent_folders()
}

# GCP-specific inputs
inputs = {
  region = "us-central1"
  zone   = "us-central1-a"
}
