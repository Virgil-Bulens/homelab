terraform {
  required_version = ">= 1.6"

  backend "s3" {
    bucket                      = "homelab-terraform-state"
    key                         = "proxmox/terraform.tfstate"
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
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.73"
    }
    unifi = {
      source  = "ubiquiti-community/unifi"
      version = "~> 0.41"
    }
    ansible = {
      source  = "ansible/ansible"
      version = "~> 1.3"
    }
  }
}

provider "proxmox" {
  endpoint  = var.proxmox_endpoint
  api_token = var.proxmox_api_token
  insecure  = true # self-signed cert on Proxmox
}

provider "unifi" {
  api_key        = var.unifi_api_key
  api_url        = var.unifi_api_url
  allow_insecure = true # self-signed cert on UniFi controller
}
