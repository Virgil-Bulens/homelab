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

# Ingress rules — only explicitly listed public hostnames are routed to the cluster.
# To expose a new app publicly: add an ingress_rule here + a cloudflare_record below,
# then re-apply Terraform. Everything else hits the catch-all 404.
resource "cloudflare_zero_trust_tunnel_cloudflared_config" "homelab" {
  account_id = var.cloudflare_account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.homelab.id

  config {
    # Required catch-all — cloudflared rejects configs without one.
    ingress_rule {
      service = "http_status:404"
    }
  }
}

# Blog — static site hosted on Cloudflare Pages, deployed via GitHub Actions.
resource "cloudflare_pages_project" "blog" {
  account_id        = var.cloudflare_account_id
  name              = "blog"
  production_branch = "main"

  build_config {
    build_command   = "hugo --minify"
    destination_dir = "public"
  }
}

resource "cloudflare_pages_domain" "blog" {
  account_id   = var.cloudflare_account_id
  project_name = cloudflare_pages_project.blog.name
  domain       = "blog.virg.be"

  depends_on = [cloudflare_pages_project.blog]
}

resource "cloudflare_record" "blog" {
  zone_id = var.cloudflare_zone_id
  name    = "blog"
  content = "${cloudflare_pages_project.blog.name}.pages.dev"
  type    = "CNAME"
  proxied = true
}

# Apex CNAME — virg.be itself points to the tunnel for the future landing page.
# Individual public app records are added alongside each ingress_rule above.
resource "cloudflare_record" "apex" {
  zone_id = var.cloudflare_zone_id
  name    = "virg.be"
  content = "${cloudflare_zero_trust_tunnel_cloudflared.homelab.id}.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
}
