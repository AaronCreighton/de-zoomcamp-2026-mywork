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
  force_destroy = true

  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "AbortIncompleteMultipartUpload"
    }
  }
}

resource "google_bigquery_dataset" "demo_dataset" {
  dataset_id = var.bq_data_name

}