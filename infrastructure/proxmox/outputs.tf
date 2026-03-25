output "control_plane_ip" {
  description = "IP address of the k3s control plane node"
  value       = var.control_plane_ip
}

output "worker_ips" {
  description = "IP addresses of the k3s worker nodes"
  value       = var.worker_ips
}

output "control_plane_vm_id" {
  description = "Proxmox VM ID of the control plane"
  value       = proxmox_virtual_environment_vm.control_plane.vm_id
}

output "worker_vm_ids" {
  description = "Proxmox VM IDs of the worker nodes"
  value       = proxmox_virtual_environment_vm.worker[*].vm_id
}
