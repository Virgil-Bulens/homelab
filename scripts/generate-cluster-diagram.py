#!/usr/bin/env python3
"""
Generate a Mermaid cluster diagram from Kubernetes manifest files.

Reads infrastructure/*/templates/*.yaml (plain YAML — no Helm rendering needed,
these are the custom resources and workload definitions written by hand) and
infrastructure/*/Chart.yaml (to infer upstream dependency workloads).

Produces a Mermaid flowchart grouped by namespace with traffic-flow edges.

Usage:
    python generate-cluster-diagram.py <infrastructure-dir> [output-file]
"""

import sys
import re
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Missing dependency: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    import hcl2
except ImportError:
    print("Missing dependency: pip install python-hcl2", file=sys.stderr)
    sys.exit(1)


# Kinds to include as diagram nodes
WORKLOAD_KINDS = {"Deployment", "DaemonSet", "StatefulSet"}
SHOWN_KINDS = WORKLOAD_KINDS | {
    "Gateway",
    "Certificate",
    "ClusterIssuer",
    "Connector",
    "CiliumLoadBalancerIPPool",
}

# Map upstream dependency chart name → (workload_name, namespace, display_label)
# These are the main workloads deployed by upstream Helm chart dependencies that
# we can't parse directly (their templates live inside the fetched chart tarball).
UPSTREAM_WORKLOADS = {
    "argo-cd":           ("argocd-server",   "argocd",               "argocd-server"),
    "cert-manager":      ("cert-manager",    "cert-manager",         "cert-manager"),
    "external-dns":      ("external-dns",    "external-dns-internal","external-dns\n(UniFi webhook)"),
    "sealed-secrets":    ("sealed-secrets",  "sealed-secrets",       "sealed-secrets"),
    "tailscale-operator":("operator",        "tailscale",            "tailscale-operator"),
}


def node_id(namespace, name):
    return re.sub(r"[^a-zA-Z0-9]", "_", f"{namespace}__{name}")


def load_docs(path):
    """Parse a YAML file that may contain multiple documents."""
    docs = []
    try:
        with open(path) as f:
            for doc in yaml.safe_load_all(f):
                if doc and isinstance(doc, dict):
                    docs.append(doc)
    except Exception as e:
        print(f"Warning: skipping {path}: {e}", file=sys.stderr)
    return docs


def load_public_hostnames(infra_dir):
    """
    Parse infrastructure/cloudflare/*.tf for Cloudflare Tunnel ingress_rule blocks
    that have an explicit hostname — these are the URLs actually exposed to the internet.
    Rules without a hostname are catch-alls and are skipped.
    """
    hostnames = set()
    cf_dir = Path(infra_dir) / "cloudflare"
    if not cf_dir.exists():
        return hostnames
    for tf_file in cf_dir.glob("*.tf"):
        try:
            with open(tf_file) as f:
                config = hcl2.load(f)
        except Exception:
            continue
        for block in config.get("resource", []):
            for instances in block.get("cloudflare_zero_trust_tunnel_cloudflared_config", {}).values():
                for cfg in instances.get("config", []):
                    for rule in cfg.get("ingress_rule", []):
                        hostname = rule.get("hostname")
                        if hostname:
                            hostnames.add(hostname)
    return hostnames


def collect(infra_dir):
    """
    Returns:
        nodes           — list of {kind, name, namespace, label}
        routes          — list of {hostname, backend_name, backend_namespace}
                          derived from HTTPRoutes (https section only)
        public_hostnames — set of hostnames actually exposed via Cloudflare Tunnel
    """
    nodes = []
    routes = []
    seen = set()

    def add_node(kind, name, namespace, label):
        key = (kind, name, namespace)
        if key not in seen:
            seen.add(key)
            nodes.append({"kind": kind, "name": name, "namespace": namespace, "label": label})

    for chart_dir in sorted(Path(infra_dir).iterdir()):
        if not chart_dir.is_dir():
            continue

        # Infer upstream workloads from Chart.yaml dependencies
        chart_yaml = chart_dir / "Chart.yaml"
        if chart_yaml.exists():
            for doc in load_docs(chart_yaml):
                for dep in doc.get("dependencies", []):
                    dep_name = dep.get("name", "")
                    if dep_name in UPSTREAM_WORKLOADS:
                        wname, wns, wlabel = UPSTREAM_WORKLOADS[dep_name]
                        add_node("Deployment", wname, wns, wlabel)

        # Parse plain-YAML template files
        templates = chart_dir / "templates"
        if not templates.exists():
            continue

        for yaml_file in sorted(templates.glob("*.yaml")):
            for doc in load_docs(yaml_file):
                kind = doc.get("kind", "")
                meta = doc.get("metadata", {})
                name = meta.get("name", "unknown")
                namespace = meta.get("namespace", "cluster-scoped")
                spec = doc.get("spec", {})

                if kind in WORKLOAD_KINDS:
                    add_node(kind, name, namespace, name)

                elif kind == "Gateway":
                    add_node(kind, name, namespace, f"{name}\n(Gateway · 192.168.2.100)")

                elif kind == "Certificate":
                    dns = spec.get("dnsNames", [name])
                    add_node(kind, name, namespace, f"{dns[0]}\n(Certificate)")

                elif kind == "ClusterIssuer":
                    add_node(kind, name, "cluster-scoped", f"{name}\n(ClusterIssuer)")

                elif kind == "Connector":
                    add_node(kind, name, namespace, f"{name}\n(Connector)")

                elif kind == "CiliumLoadBalancerIPPool":
                    blocks = spec.get("blocks", [{}])
                    start = blocks[0].get("start", "?")
                    stop = blocks[0].get("stop", "?")
                    add_node(kind, name, "cluster-scoped", f"LB pool\n{start}–{stop}")

                elif kind == "HTTPRoute":
                    # Only emit traffic edges for HTTPS routes that have real backends.
                    # Redirect-only routes (no backendRefs) are skipped — they're plumbing,
                    # not meaningful topology.
                    parent_section = next(
                        (p.get("sectionName", "") for p in spec.get("parentRefs", [])), ""
                    )
                    if parent_section != "https":
                        continue
                    hostnames = spec.get("hostnames", [name])
                    for rule in spec.get("rules", []):
                        for backend in rule.get("backendRefs", []):
                            routes.append({
                                "hostname": hostnames[0],
                                "backend_name": backend["name"],
                                "backend_namespace": namespace,
                            })

    public_hostnames = load_public_hostnames(infra_dir)
    return nodes, routes, public_hostnames


def generate(nodes, routes, public_hostnames):
    lines = ["```mermaid", "flowchart TD"]

    # Group by namespace
    by_ns = {}
    for n in nodes:
        by_ns.setdefault(n["namespace"], []).append(n)

    # Build node ID index for edge generation
    id_map = {}  # (name, namespace) → mermaid node id
    for n in nodes:
        nid = node_id(n["namespace"], n["name"])
        id_map[(n["name"], n["namespace"])] = nid

    gw_id = id_map.get(("homelab", "networking"))
    cfd_id = id_map.get(("cloudflared", "cloudflared"))
    connector_id = id_map.get(("homelab-subnet-router", "tailscale"))

    # Public routes: HTTPRoutes whose hostname is in the Cloudflare Tunnel ingress config
    public_routes = [r for r in routes if r["hostname"] in public_hostnames]

    # External block — only include Internet node if something is actually public
    lines.append('    subgraph external["External"]')
    if public_routes:
        lines.append('        internet["Internet"]')
    lines.append('        lan["LAN (192.168.2.x)"]')
    lines.append('        ts_net["Tailscale Network"]')
    lines.append("    end")

    # Namespace subgraphs — cluster-scoped last
    def ns_order(ns):
        order = ["networking", "argocd", "cloudflared", "external-dns-internal",
                 "cert-manager", "sealed-secrets", "tailscale", "cluster-scoped"]
        return order.index(ns) if ns in order else len(order)

    for ns in sorted(by_ns, key=ns_order):
        ns_label = ns.replace("-", "‑")  # non-breaking hyphen for Mermaid label
        lines.append(f'    subgraph {node_id(ns, "ns")}["{ns_label}"]')
        for n in by_ns[ns]:
            nid = node_id(n["namespace"], n["name"])
            label = n["label"].replace("\n", "\\n")
            lines.append(f'        {nid}["{label}"]')
        lines.append("    end")

    # LAN → Gateway (L2 announcement — always present)
    if gw_id:
        lines.append(f"    lan --> {gw_id}")

    # Cloudflare Tunnel: only draw if there are actual public ingress rules
    if public_routes and cfd_id and gw_id:
        lines.append(f"    internet --> {cfd_id}")
        lines.append(f"    {cfd_id} --> {gw_id}")

    # Tailscale subnet router
    if connector_id:
        lines.append(f"    ts_net --> {connector_id}")

    # Gateway → backend edges, labelled with hostname.
    # Public routes get an extra "(public)" marker on the edge.
    public_hostnames_set = {r["hostname"] for r in public_routes}
    for route in routes:
        backend_id = id_map.get((route["backend_name"], route["backend_namespace"]))
        if backend_id and gw_id:
            suffix = " ⬡" if route["hostname"] in public_hostnames_set else ""
            lines.append(f'    {gw_id} -->|"{route["hostname"]}{suffix}"| {backend_id}')

    lines.append("```")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <infrastructure-dir> [output-file]", file=sys.stderr)
        sys.exit(1)

    infra_dir = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    nodes, routes, public_hostnames = collect(infra_dir)
    diagram = generate(nodes, routes, public_hostnames)

    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(output_file).write_text(diagram + "\n")
        print(f"Written to {output_file}", file=sys.stderr)
    else:
        print(diagram)
