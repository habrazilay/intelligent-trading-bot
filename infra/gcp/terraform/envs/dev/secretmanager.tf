# -----------------------------------------------------------------------------
# Secret Manager - Binance Credentials
# -----------------------------------------------------------------------------

resource "google_secret_manager_secret" "binance_api_key" {
  secret_id = "binance-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    purpose     = "binance-trading"
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "binance_api_key" {
  secret      = google_secret_manager_secret.binance_api_key.id
  secret_data = var.binance_api_key
}

resource "google_secret_manager_secret" "binance_api_secret" {
  secret_id = "binance-api-secret"
  project   = var.project_id

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    purpose     = "binance-trading"
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "binance_api_secret" {
  secret      = google_secret_manager_secret.binance_api_secret.id
  secret_data = var.binance_api_secret
}
