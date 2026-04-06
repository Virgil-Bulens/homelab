variable "cloudflare_api_token" {
  description = "Cloudflare API token (R2:Edit + Account:Read)"
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID"
  type        = string
}
