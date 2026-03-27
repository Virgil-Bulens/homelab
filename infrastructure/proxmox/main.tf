resource "proxmox_virtual_environment_vm" "control_plane" {
  name      = "k3s-cp-1"
  node_name = var.proxmox_node
  vm_id     = 200

  clone {
    vm_id     = var.template_vm_id
    node_name = var.proxmox_node
    full      = true
  }

  agent {
    enabled = true
  }

  cpu {
    cores = var.control_plane_cores
    type  = "host"
  }

  memory {
    dedicated = var.control_plane_memory
  }

  disk {
    datastore_id = var.datastore
    interface    = "scsi0"
    size         = var.control_plane_disk_size
  }

  network_device {
    bridge      = "vmbr0"
    model       = "virtio"
    mac_address = var.control_plane_mac
  }

  initialization {
    datastore_id = var.datastore

    ip_config {
      ipv4 {
        address = "${var.control_plane_ip}/24"
        gateway = var.network_gateway
      }
    }

    user_account {
      username = "admin"
      keys     = [var.ssh_public_key]
    }

    dns {
      server = var.dns_server
    }
  }

  on_boot = true
}

resource "proxmox_virtual_environment_vm" "worker" {
  count     = length(var.worker_ips)
  name      = "k3s-worker-${count.index + 1}"
  node_name = var.proxmox_node
  vm_id     = 210 + count.index

  clone {
    vm_id     = var.template_vm_id
    node_name = var.proxmox_node
    full      = true
  }

  agent {
    enabled = true
  }

  cpu {
    cores = var.worker_cores
    type  = "host"
  }

  memory {
    dedicated = var.worker_memory
  }

  disk {
    datastore_id = var.datastore
    interface    = "scsi0"
    size         = var.worker_disk_size
  }

  network_device {
    bridge      = "vmbr0"
    model       = "virtio"
    mac_address = var.worker_macs[count.index]
  }

  initialization {
    datastore_id = var.datastore

    ip_config {
      ipv4 {
        address = "${var.worker_ips[count.index]}/24"
        gateway = var.network_gateway
      }
    }

    user_account {
      username = "admin"
      keys     = [var.ssh_public_key]
    }

    dns {
      server = var.dns_server
    }
  }

  on_boot = true
}
