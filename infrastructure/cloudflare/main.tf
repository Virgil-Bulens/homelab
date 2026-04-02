# Named tunnel — credentials are managed by Cloudflare, referenced in-cluster via TUNNEL_TOKEN.
resource "cloudflare_zero_trust_tunnel_cloudflared" "homelab" {
  account_id = var.cloudflare_account_id
  name       = "homelab"
  secret     = random_id.tunnel_secret.b64_std
}

# 32-byte random secret required by the tunnel resource.
resource "random_id" "tunnel_secret" {
  byte_length = 32
}

# Ingress rules define how cloudflared routes incoming requests to cluster services.
# All *.virg.be traffic is sent to the cluster Gateway; anything else gets a 404.
# To add a new public hostname, add an ingress_rule above the catch-all and re-apply.
resource "cloudflare_zero_trust_tunnel_cloudflared_config" "homelab" {
  account_id = var.cloudflare_account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.homelab.id

  config {
    ingress_rule {
      hostname = "*.virg.be"
      # Gateway service in the networking namespace — cloudflared reaches it via cluster DNS.
      service = "http://homelab.networking.svc.cluster.local:80"
    }
    ingress_rule {
      hostname = "virg.be"
      service  = "http://homelab.networking.svc.cluster.local:80"
    }
    # Required catch-all — cloudflared rejects configs without one.
    ingress_rule {
      service = "http_status:404"
    }
  }
}

# Wildcard CNAME routes all *.virg.be public DNS through the tunnel.
# proxied = true is required — the tunnel only works via Cloudflare's proxy.
resource "cloudflare_record" "wildcard" {
  zone_id = var.cloudflare_zone_id
  name    = "*"
  content = "${cloudflare_zero_trust_tunnel_cloudflared.homelab.id}.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
}

resource "cloudflare_record" "apex" {
  zone_id        = var.cloudflare_zone_id
  name           = "virg.be"
  content        = "${cloudflare_zero_trust_tunnel_cloudflared.homelab.id}.cfargotunnel.com"
  type           = "CNAME"
  proxied = true
}
