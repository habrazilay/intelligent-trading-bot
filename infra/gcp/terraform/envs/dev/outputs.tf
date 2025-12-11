# -----------------------------------------------------------------------------
# Project
# -----------------------------------------------------------------------------

output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

# -----------------------------------------------------------------------------
# Service Account
# -----------------------------------------------------------------------------

output "ml_service_account_email" {
  value = google_service_account.ml_service_account.email
}

# -----------------------------------------------------------------------------
# Storage
# -----------------------------------------------------------------------------

output "data_bucket_name" {
  value = google_storage_bucket.data.name
}

output "data_bucket_url" {
  value = google_storage_bucket.data.url
}

output "models_bucket_name" {
  value = google_storage_bucket.models.name
}

output "models_bucket_url" {
  value = google_storage_bucket.models.url
}

# -----------------------------------------------------------------------------
# Vertex AI
# -----------------------------------------------------------------------------

output "workbench_instance_name" {
  value = google_notebooks_instance.ml_workbench.name
}

output "metadata_store_name" {
  value = google_vertex_ai_metadata_store.default.name
}
