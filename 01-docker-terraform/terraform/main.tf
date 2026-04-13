terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.27.0"
    }
  }
}

provider "google" {
  project = "de-zoomcamp-terraform-493201"
  region  = "australia-southeast1"
}

resource "google_storage_bucket" "demo-bucket" {
  name          = "de-zoomcamp-terraform-493122-terraform-bucket"
  location      = "australia-southeast1"
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
  dataset_id = "demo_dataset"

}