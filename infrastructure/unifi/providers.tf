terraform {
  required_version = ">= 1.6"

  backend "s3" {
    bucket                      = "homelab-terraform-state"
    key                         = "unifi/terraform.tfstate"
    region                      = "auto"
    endpoints = {
      s3 = "https://c3aead5e648abe8b77607055ef68508d.r2.cloudflarestorage.com"
    }
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    force_path_style            = true
  }

  required_providers {
    unifi = {
      source  = "ubiquiti-community/unifi"
      version = "~> 0.41" # run terraform plan/apply with -parallelism=1 (provider has concurrent map race)
    }
  }
}

provider "unifi" {
  api_key        = var.unifi_api_key
  api_url        = var.unifi_api_url
  allow_insecure = true # self-signed cert on UniFi controller
}
