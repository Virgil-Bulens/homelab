terraform {
  required_version = ">= 1.6"

  backend "s3" {
    bucket                      = "homelab-terraform-state"
    key                         = "cloudflare/terraform.tfstate"
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
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
