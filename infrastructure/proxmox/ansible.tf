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

resource "ansible_host" "ai_worker" {
  name   = proxmox_virtual_environment_vm.ai_worker.name
  groups = ["ai_workers", "k3s"]

  variables = {
    ansible_host = var.ai_worker_ip
    ansible_user = "admin"
    k3s_role     = "agent"
  }
}
