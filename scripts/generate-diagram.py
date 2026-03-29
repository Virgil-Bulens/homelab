#!/usr/bin/env python3
"""
Generate a Mermaid architecture diagram from Terraform HCL files.

Reads resources and variable defaults from .tf files — no credentials or
terraform init required. Outputs a Mermaid flowchart to stdout or a file.

Usage:
    python generate-diagram.py <terraform-dir> [output-file]
"""

import sys
import json
import re
from pathlib import Path

try:
    import hcl2
except ImportError:
    print("Missing dependency: pip install python-hcl2", file=sys.stderr)
    sys.exit(1)


def load_tf_dir(directory):
    """Parse all .tf files in a directory, returning merged resources and variables."""
    resources = {}
    variables = {}

    for tf_file in sorted(Path(directory).glob("*.tf")):
        with open(tf_file) as f:
            try:
                config = hcl2.load(f)
            except Exception as e:
                print(f"Warning: could not parse {tf_file.name}: {e}", file=sys.stderr)
                continue

        for block in config.get("resource", []):
            for resource_type, instances in block.items():
                for name, attrs in instances.items():
                    resources.setdefault(resource_type, {})[name] = attrs

        for block in config.get("variable", []):
            for var_name, var_attrs in block.items():
                if "default" in var_attrs:
                    variables[var_name] = var_attrs["default"]

    return resources, variables


def resolve(value, variables):
    """Resolve a ${var.name} reference to its default value."""
    if isinstance(value, str):
        match = re.match(r'^\$\{var\.(\w+)\}$', value)
        if match:
            return variables.get(match.group(1), value)
    return value


def generate(resources, variables):
    lines = [
        "```mermaid",
        "flowchart TD",
    ]

    # --- Proxmox VMs ---
    cp_ip = variables.get("control_plane_ip", "?")
    worker_ips = variables.get("worker_ips", [])
    dns_domain = variables.get("dns_domain", "lan")

    lines.append('    subgraph Proxmox["Proxmox (pve)"]')
    lines.append(f'        vm_cp["k3s-cp-1\\nVM 200 · {cp_ip}\\ncontrol-plane"]')
    for i, ip in enumerate(worker_ips):
        lines.append(f'        vm_w{i+1}["k3s-worker-{i+1}\\nVM {210+i} · {ip}\\nworker"]')
    lines.append("    end")

    # --- UniFi ---
    lines.append('    subgraph UniFi["UniFi (192.168.1.1)"]')
    lines.append(f'        dhcp_cp["DHCP\\n{cp_ip}"]')
    lines.append(f'        dns_cp["DNS\\nk3s-cp-1.{dns_domain} → {cp_ip}"]')
    for i, ip in enumerate(worker_ips):
        lines.append(f'        dhcp_w{i+1}["DHCP\\n{ip}"]')
        lines.append(f'        dns_w{i+1}["DNS\\nk3s-worker-{i+1}.{dns_domain} → {ip}"]')
    lines.append("    end")

    # --- Ansible inventory ---
    lines.append('    subgraph Ansible["Ansible Inventory"]')
    lines.append('        ans_cp["control_plane\\nk3s server"]')
    lines.append('        ans_w["workers\\nk3s agents"]')
    lines.append("    end")

    # --- Edges: VMs → UniFi ---
    lines.append("    vm_cp --> dhcp_cp")
    lines.append("    vm_cp --> dns_cp")
    for i in range(len(worker_ips)):
        lines.append(f"    vm_w{i+1} --> dhcp_w{i+1}")
        lines.append(f"    vm_w{i+1} --> dns_w{i+1}")

    # --- Edges: VMs → Ansible ---
    lines.append("    vm_cp --> ans_cp")
    for i in range(len(worker_ips)):
        lines.append(f"    vm_w{i+1} --> ans_w")

    lines.append("```")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <terraform-dir> [output-file]", file=sys.stderr)
        sys.exit(1)

    tf_dir = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    resources, variables = load_tf_dir(tf_dir)
    diagram = generate(resources, variables)

    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(output_file).write_text(diagram + "\n")
        print(f"Written to {output_file}", file=sys.stderr)
    else:
        print(diagram)
