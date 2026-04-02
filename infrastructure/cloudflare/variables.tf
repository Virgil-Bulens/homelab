variable "cloudflare_api_token" {
  description = "Cloudflare API token (Tunnel:Edit + DNS:Edit + Zone:Read)"
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID"
  type        = string
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for virg.be"
  type        = string
}
