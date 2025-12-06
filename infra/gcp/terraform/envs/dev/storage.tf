# -----------------------------------------------------------------------------
# Cloud Storage Bucket - Training Data
# -----------------------------------------------------------------------------

resource "google_storage_bucket" "data" {
  name          = "${var.project_name}-data-${var.environment}-${var.project_id}"
  location      = var.region
  force_destroy = false  # Protect data from accidental deletion

  # Lifecycle rules
  lifecycle_rule {
    condition {
      age = 90  # Move to coldline after 90 days
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  # Versioning for data protection
  versioning {
    enabled = true
  }

  # Uniform bucket-level access (recommended)
  uniform_bucket_level_access = true

  labels = {
    environment = var.environment
    project     = var.project_name
    purpose     = "ml-training-data"
  }

  depends_on = [google_project_service.apis]
}

# -----------------------------------------------------------------------------
# Cloud Storage Bucket - Models
# -----------------------------------------------------------------------------

resource "google_storage_bucket" "models" {
  name          = "${var.project_name}-models-${var.environment}-${var.project_id}"
  location      = var.region
  force_destroy = false

  versioning {
    enabled = true  # Important for model versioning
  }

  uniform_bucket_level_access = true

  labels = {
    environment = var.environment
    project     = var.project_name
    purpose     = "ml-models"
  }

  depends_on = [google_project_service.apis]
}

# -----------------------------------------------------------------------------
# Folder Structure (using empty objects as markers)
# -----------------------------------------------------------------------------

resource "google_storage_bucket_object" "data_folders" {
  for_each = toset([
    "raw/BTCUSDT/",
    "raw/ETHUSDT/",
    "raw/BNBUSDT/",
    "raw/SOLUSDT/",
    "raw/XRPUSDT/",
    "processed/",
    "predictions/",
    "logs/",
  ])

  name    = each.key
  content = ""
  bucket  = google_storage_bucket.data.name
}
