terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.27.0"
    }
  }
}

provider "google" {
  credentials = file(var.credentials)
  project     = var.project
  region      = var.location
}

resource "google_storage_bucket" "demo-bucket" {
  name          = "${var.project}-${var.gcs_bucket_name}"
  location      = var.location
  uniform_bucket_level_access = true
  force_destroy = true

  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "AbortIncompleteMultipartUpload"
    }
  }

  lifecycle_rule {
    condition {
      age            = 30
      matches_prefix = ["taxi/raw/"]
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
}

resource "google_bigquery_dataset" "demo_dataset" {
  dataset_id = var.bq_data_name

}