variable "credentials" {
  description = "The path to the GCP credentials file."
  type        = string
  default     = "./keys/my-creds.json"
}



variable "project" {
  description = "The GCP project to use for creating resources."
  type        = string
  default     = "de-zoomcamp-terraform-493201"

}


variable "location" {
  description = "The location of the resources to create."
  type        = string
  default     = "australia-southeast1"
}



variable "bq_data_name" {
  description = "The name of the BigQuery dataset to create."
  type        = string
  default     = "demo_dataset"
}

variable "gcs_bucket_name" {
  description = "The name of the GCS bucket to create."
  type        = string
  default     = "demo-bucket"
}

variable "gcs_storgage_class" {
  description = "The storage class of the GCS bucket to create."
  type        = string
  default     = "STANDARD"

}