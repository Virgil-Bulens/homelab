output "velero_r2_bucket_name" {
  value = cloudflare_r2_bucket.velero.name
}

output "velero_r2_api_token" {
  value     = cloudflare_api_token.velero_r2.value
  sensitive = true
}

# R2 S3-compatible endpoint for this account — plug into Velero values.yaml
output "velero_r2_endpoint" {
  value = "https://${var.cloudflare_account_id}.r2.cloudflarestorage.com"
}
