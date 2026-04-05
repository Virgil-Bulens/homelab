# DNS configuration for the homelab tailnet.

# Global nameserver — used for all queries not matched by split DNS rules.
resource "tailscale_dns_nameservers" "global" {
  nameservers = [
    "194.242.2.2", # Mullvad DNS (no-logging, no-filtering)
  ]
}

# Split DNS — virg.be resolves via the UniFi resolver when on Tailscale.
# Without this, devices on 5G/remote resolve *.virg.be to Cloudflare public
# records instead of 192.168.2.100, bypassing the subnet router route.
resource "tailscale_dns_split_nameservers" "virg_be" {
  domain      = "virg.be"
  nameservers = ["192.168.1.1"]
}

# MagicDNS — assigns DNS names to tailnet devices by machine name.
resource "tailscale_dns_preferences" "main" {
  magic_dns = true
}
