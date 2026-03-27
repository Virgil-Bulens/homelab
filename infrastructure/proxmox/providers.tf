terraform {
  required_version = ">= 1.6"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.73"
    }
    unifi = {
      source  = "ubiquiti-community/unifi"
      version = "~> 0.41"
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
