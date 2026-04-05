# DNS records and static client assignments

resource "unifi_dns_record" "control_plane" {
  name        = "k3s-cp-1.${var.dns_domain}"
  record_type = "A"
  value       = var.control_plane_ip
}

resource "unifi_dns_record" "worker" {
  count       = length(var.worker_ips)
  name        = "k3s-worker-${count.index + 1}.${var.dns_domain}"
  record_type = "A"
  value       = var.worker_ips[count.index]
}

# Firewall — allow MacBook VLAN to reach the cluster Gateway on HTTP/HTTPS.
# Without this, inter-VLAN traffic from 192.168.3.x to 192.168.2.100 is blocked.

resource "unifi_firewall_group" "clients_vlan" {
  name    = "clients-vlan"
  type    = "address-group"
  members = ["192.168.3.0/24"]
}

resource "unifi_firewall_group" "k8s_gateway" {
  name    = "k8s-gateway"
  type    = "address-group"
  members = ["192.168.2.100"]
}

# unifi_firewall_rule "clients_to_gateway" is intentionally NOT managed here.
# ubiquiti-community/unifi provider (v0.41.x) hardcodes rule_index validation to
# 2000-2999 / 4000-4999, but this UniFi OS version assigns LAN_IN rules at 10000+.
# The provider bug is tracked at: github.com/ubiquiti-community/terraform-provider-unifi/issues/142
# Rule was created manually in the UI: "allow-clients-to-k8s-gateway", index 10012,
# LAN_IN, accept TCP 80/443, src=clients-vlan group, dst=k8s-gateway group.

# DHCP reservations

resource "unifi_client" "control_plane" {
  mac        = var.control_plane_mac
  name       = "k3s-cp-1"
  fixed_ip   = var.control_plane_ip
  network_id = var.servers_network_id
}

resource "unifi_client" "worker" {
  count      = length(var.worker_ips)
  mac        = var.worker_macs[count.index]
  name       = "k3s-worker-${count.index + 1}"
  fixed_ip   = var.worker_ips[count.index]
  network_id = var.servers_network_id
}
