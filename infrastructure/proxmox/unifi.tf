data "unifi_network" "vms" {
  name = var.unifi_network_name
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

resource "unifi_user" "control_plane" {
  mac        = var.control_plane_mac
  name       = "k3s-cp-1"
  fixed_ip   = var.control_plane_ip
  network_id = data.unifi_network.vms.id
}

resource "unifi_user" "worker" {
  count      = length(var.worker_ips)
  mac        = var.worker_macs[count.index]
  name       = "k3s-worker-${count.index + 1}"
  fixed_ip   = var.worker_ips[count.index]
  network_id = data.unifi_network.vms.id
}
