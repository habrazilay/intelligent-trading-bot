# -----------------------------------------------------------------------------
# Enable Required APIs
# -----------------------------------------------------------------------------

resource "google_project_service" "apis" {
  for_each = toset([
    "storage.googleapis.com",           # Cloud Storage
    "aiplatform.googleapis.com",         # Vertex AI
    "secretmanager.googleapis.com",      # Secret Manager
    "compute.googleapis.com",            # Compute Engine (for Vertex AI)
    "containerregistry.googleapis.com",  # Container Registry
    "cloudbuild.googleapis.com",         # Cloud Build
    "notebooks.googleapis.com",          # Vertex AI Workbench
  ])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# -----------------------------------------------------------------------------
# Service Account for ML Workloads
# -----------------------------------------------------------------------------

resource "google_service_account" "ml_service_account" {
  account_id   = "${var.project_name}-ml-${var.environment}"
  display_name = "ML Service Account for ${var.project_name}"
  project      = var.project_id

  depends_on = [google_project_service.apis]
}

# Grant necessary roles to service account
resource "google_project_iam_member" "ml_roles" {
  for_each = toset([
    "roles/aiplatform.user",           # Vertex AI
    "roles/storage.objectAdmin",       # GCS read/write
    "roles/secretmanager.secretAccessor", # Read secrets
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.ml_service_account.email}"
}
