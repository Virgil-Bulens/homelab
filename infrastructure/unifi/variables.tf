variable "unifi_api_key" {
  description = "UniFi controller API key"
  type        = string
  sensitive   = true
}

variable "unifi_api_url" {
  description = "UniFi controller URL"
  type        = string
  default     = "https://192.168.1.1"
}

variable "dns_domain" {
  description = "Local DNS domain (e.g. lan)"
  type        = string
  default     = "lan"
}

variable "control_plane_ip" {
  description = "Static IP for the control plane node"
  type        = string
  default     = "192.168.2.10"
}

variable "control_plane_mac" {
  description = "MAC address for the control plane VM (locally administered)"
  type        = string
  default     = "02:ab:00:00:00:01"
}

variable "worker_ips" {
  description = "Static IPs for worker nodes"
  type        = list(string)
  default     = ["192.168.2.11", "192.168.2.12"]
}

variable "worker_macs" {
  description = "MAC addresses for worker VMs — must match length of worker_ips"
  type        = list(string)
  default     = ["02:ab:00:00:00:02", "02:ab:00:00:00:03"]
}

variable "servers_network_id" {
  description = "UniFi network ID for the servers VLAN"
  type        = string
  default     = "604e678a8729b304a1a35067"
}
