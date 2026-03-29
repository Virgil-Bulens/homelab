resource "ansible_host" "control_plane" {
  name   = proxmox_virtual_environment_vm.control_plane.name
  groups = ["control_plane", "k3s"]

  variables = {
    ansible_host = var.control_plane_ip
    ansible_user = "admin"
    k3s_role     = "server"
  }
}

resource "ansible_host" "workers" {
  count  = length(var.worker_ips)
  name   = proxmox_virtual_environment_vm.worker[count.index].name
  groups = ["workers", "k3s"]

  variables = {
    ansible_host = var.worker_ips[count.index]
    ansible_user = "admin"
    k3s_role     = "agent"
  }
}
