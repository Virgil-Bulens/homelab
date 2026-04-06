# R2 bucket for Velero backups.
# Separate module from infrastructure/cloudflare/ — avoids state entanglement
# between backup storage and DNS/Tunnel resources.
resource "cloudflare_r2_bucket" "velero" {
  account_id = var.cloudflare_account_id
  name       = "homelab-velero-backups"
  location   = "WEUR"
}

# Scoped API token — Velero only needs R2 read/write, nothing else.
resource "cloudflare_api_token" "velero_r2" {
  name = "velero-r2"

  policy {
    permission_groups = [
      data.cloudflare_api_token_permission_groups.all.account["Workers R2 Storage Write"],
    ]
    resources = {
      "com.cloudflare.api.account.${var.cloudflare_account_id}" = "*"
    }
  }
}

data "cloudflare_api_token_permission_groups" "all" {}
