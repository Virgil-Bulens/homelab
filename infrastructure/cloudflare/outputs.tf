output "tunnel_id" {
  description = "Tunnel ID — used in cloudflared config and CNAME value"
  value       = cloudflare_zero_trust_tunnel_cloudflared.homelab.id
}

# Seal this value and commit it as infrastructure/cloudflared/templates/sealed-secret.yaml.
# Steps:
#   terraform output -raw tunnel_token | \
#     kubeseal --raw --from-file=/dev/stdin \
#              --namespace cloudflared --name cloudflared-token \
#              --controller-name=sealed-secrets --controller-namespace=sealed-secrets
# Then wrap the output in the SealedSecret manifest (see existing examples in the repo).
output "tunnel_token" {
  description = "Tunnel token — seal with kubeseal before committing"
  value       = cloudflare_zero_trust_tunnel_cloudflared.homelab.tunnel_token
  sensitive   = true
}
