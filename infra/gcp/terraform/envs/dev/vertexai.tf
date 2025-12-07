# -----------------------------------------------------------------------------
# Vertex AI - Training Configuration
# -----------------------------------------------------------------------------

# Note: Vertex AI training jobs are typically created via API/SDK
# This file sets up the infrastructure and permissions

# -----------------------------------------------------------------------------
# Vertex AI Workbench Instance (for development/experimentation)
# -----------------------------------------------------------------------------

resource "google_notebooks_instance" "ml_workbench" {
  name         = "${var.project_name}-workbench-${var.environment}"
  location     = var.zone
  machine_type = "n1-standard-4"  # 4 vCPU, 15 GB RAM

  vm_image {
    project      = "deeplearning-platform-release"
    image_family = "tf-latest-cpu"  # TensorFlow pre-installed
  }

  # Use the ML service account
  service_account = google_service_account.ml_service_account.email

  # Auto-shutdown to save costs
  metadata = {
    idle-timeout-seconds = "3600"  # 1 hour
  }

  # Disk configuration
  boot_disk_type    = "PD_SSD"
  boot_disk_size_gb = 100

  # No public IP for security (access via IAP)
  no_public_ip = false  # Set true in production

  labels = {
    environment = var.environment
    project     = var.project_name
    purpose     = "ml-development"
  }

  depends_on = [
    google_project_service.apis,
    google_service_account.ml_service_account
  ]
}

# -----------------------------------------------------------------------------
# Vertex AI Metadata Store (for experiment tracking)
# -----------------------------------------------------------------------------

resource "google_vertex_ai_metadata_store" "default" {
  name        = "${var.project_name}-metadata-${var.environment}"
  description = "Metadata store for ML experiments"
  region      = var.region
  project     = var.project_id

  depends_on = [google_project_service.apis]
}
