locals {
  # Hardcoded due to provider bug: data "unifi_network" name lookup fails on UDM Pro 3.x
  # (dhcpd_enabled returned as string instead of bool, breaks JSON deserialisation)
  servers_network_id = "604e678a8729b304a1a35067"
}

# DNS records

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

# DHCP reservations

resource "unifi_client" "control_plane" {
  mac        = var.control_plane_mac
  name       = "k3s-cp-1"
  fixed_ip   = var.control_plane_ip
  network_id = local.servers_network_id
}

resource "unifi_client" "worker" {
  count      = length(var.worker_ips)
  mac        = var.worker_macs[count.index]
  name       = "k3s-worker-${count.index + 1}"
  fixed_ip   = var.worker_ips[count.index]
  network_id = local.servers_network_id
}
