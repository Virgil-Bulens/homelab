terraform {
  required_version = ">= 1.6"

  backend "s3" {
    bucket                      = "homelab-terraform-state"
    key                         = "tailscale/terraform.tfstate"
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
    tailscale = {
      source  = "tailscale/tailscale"
      version = "~> 0.17"
    }
  }
}

provider "tailscale" {
  oauth_client_id     = var.tailscale_oauth_client_id
  oauth_client_secret = var.tailscale_oauth_client_secret
  tailnet             = var.tailnet
}
