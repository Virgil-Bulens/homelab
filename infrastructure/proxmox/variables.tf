variable "proxmox_endpoint" {
  description = "Proxmox API endpoint, e.g. https://192.168.2.9:8006"
  type        = string
}

variable "proxmox_api_token" {
  description = "Proxmox API token in the form user@realm!token=secret"
  type        = string
  sensitive   = true
}

variable "proxmox_node" {
  description = "Proxmox node name"
  type        = string
  default     = "pve"
}

variable "template_vm_id" {
  description = "VM ID of the Debian cloud-init template to clone"
  type        = number
  default     = 1001
}

variable "ssh_public_key" {
  description = "SSH public key to inject into all VMs"
  type        = string
  sensitive   = true
}

variable "network_gateway" {
  description = "Default gateway for all VMs"
  type        = string
  default     = "192.168.2.1"
}

variable "dns_server" {
  description = "DNS server for all VMs"
  type        = string
  default     = "192.168.2.1"
}

variable "datastore" {
  description = "Proxmox storage pool for VM disks and cloud-init drives"
  type        = string
  default     = "local-lvm"
}

# Control plane

variable "control_plane_ip" {
  description = "Static IP for the control plane node (without prefix length)"
  type        = string
  default     = "192.168.2.10"
}

variable "control_plane_cores" {
  type    = number
  default = 2
}

variable "control_plane_memory" {
  description = "Memory in MB"
  type        = number
  default     = 4096
}

variable "control_plane_disk_size" {
  description = "Disk size in GB"
  type        = number
  default     = 30
}

# Workers

variable "worker_ips" {
  description = "Static IPs for worker nodes (without prefix length)"
  type        = list(string)
  default     = ["192.168.2.11", "192.168.2.12"]
}

variable "worker_cores" {
  type    = number
  default = 4
}

variable "worker_memory" {
  description = "Memory in MB"
  type        = number
  default     = 8192
}

variable "worker_disk_size" {
  description = "Disk size in GB"
  type        = number
  default     = 80
}

variable "control_plane_mac" {
  description = "MAC address for the control plane VM (locally administered)"
  type        = string
  default     = "02:ab:00:00:00:01"
}

variable "worker_macs" {
  description = "MAC addresses for worker VMs — must match length of worker_ips"
  type        = list(string)
  default     = ["02:ab:00:00:00:02", "02:ab:00:00:00:03"]
}
