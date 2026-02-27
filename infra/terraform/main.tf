# =============================================================================
# FCT Proposal Engine — GCP Infrastructure (Terraform)
# =============================================================================

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "fct-proposal-engine-tfstate"
    prefix = "terraform/state"
  }
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "fct-proposal-engine"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west1"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "fct-engine-api"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# --- Enable APIs ---
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudbuild.googleapis.com",
    "firestore.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# --- Artifact Registry ---
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "fct-engine"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# --- Secret Manager (API Keys) ---
locals {
  secrets = [
    "anthropic-api-key",
    "openai-api-key",
    "google-api-key",
    "huggingface-api-key",
    "scopus-api-key",
  ]
}

resource "google_secret_manager_secret" "api_keys" {
  for_each  = toset(local.secrets)
  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# --- Service Account ---
resource "google_service_account" "runner" {
  account_id   = "${var.service_name}-sa"
  display_name = "FCT Engine Cloud Run SA"
}

resource "google_secret_manager_secret_iam_member" "runner_access" {
  for_each  = toset(local.secrets)
  secret_id = google_secret_manager_secret.api_keys[each.value].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runner.email}"
}

# --- Cloud Storage (proposal outputs) ---
resource "google_storage_bucket" "proposals" {
  name                        = "${var.project_id}-proposals"
  location                    = var.region
  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket_iam_member" "runner_storage" {
  bucket = google_storage_bucket.proposals.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runner.email}"
}

# --- Cloud Run Service ---
resource "google_cloud_run_v2_service" "api" {
  name     = var.service_name
  location = var.region

  template {
    service_account = google_service_account.runner.email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/fct-engine/${var.service_name}:latest"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCS_BUCKET"
        value = google_storage_bucket.proposals.name
      }

      dynamic "env" {
        for_each = {
          "ANTHROPIC_API_KEY"    = "anthropic-api-key"
          "OPENAI_API_KEY"       = "openai-api-key"
          "GOOGLE_API_KEY"       = "google-api-key"
          "HUGGINGFACE_API_KEY"  = "huggingface-api-key"
          "SCOPUS_API_KEY"       = "scopus-api-key"
        }
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_iam_member.runner_access,
  ]
}

# --- Allow unauthenticated access (or restrict as needed) ---
resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- Outputs ---
output "service_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "artifact_registry" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/fct-engine"
}
