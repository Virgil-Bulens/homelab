#!/usr/bin/env python3
"""
Generate a Mermaid cluster diagram from Kubernetes manifest files.

Sources (no external downloads, no helm rendering):
  - infrastructure/*/templates/*.yaml   hand-written resources:
      Gateway, Certificate, ClusterIssuer, Connector, CiliumLoadBalancerIPPool,
      and HTTPRoutes (HTTPS backends become workload nodes automatically)
  - infrastructure/*/Chart.yaml         dependency names become infrastructure nodes
  - infrastructure/cloudflare/*.tf      Cloudflare Tunnel ingress rules (public hostnames)

Adding a new app with an HTTPRoute automatically adds it to the diagram.
Adding a new infra chart automatically adds its dependency names as nodes.

Usage:
    python generate-cluster-diagram.py <infrastructure-dir> [output-file]
    # clusters/ is inferred from infrastructure/../clusters/home/infrastructure/
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


HAND_WRITTEN_KINDS = {
    "Gateway",
    "Certificate",
    "ClusterIssuer",
    "Connector",
    "CiliumLoadBalancerIPPool",
}


def node_id(namespace, name):
    return re.sub(r"[^a-zA-Z0-9]", "_", f"{namespace}__{name}")


def load_docs(path):
    docs = []
    try:
        with open(path) as f:
            for doc in yaml.safe_load_all(f):
                if doc and isinstance(doc, dict):
                    docs.append(doc)
    except Exception as e:
        print(f"Warning: skipping {path}: {e}", file=sys.stderr)
    return docs


def load_app_namespaces(clusters_dir):
    """
    Parse clusters/home/infrastructure/*.yaml → {chart_dir_name: destination_namespace}.
    """
    ns_map = {}
    app_dir = Path(clusters_dir)
    if not app_dir.exists():
        return ns_map
    for app_file in app_dir.glob("*.yaml"):
        for doc in load_docs(app_file):
            if doc.get("kind") != "Application":
                continue
            path = doc.get("spec", {}).get("source", {}).get("path", "")
            namespace = doc.get("spec", {}).get("destination", {}).get("namespace", "")
            if path and namespace:
                ns_map[Path(path).name] = namespace
    return ns_map


def load_public_hostnames(infra_dir):
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
            for instances in block.get(
                "cloudflare_zero_trust_tunnel_cloudflared_config", {}
            ).values():
                for cfg in instances.get("config", []):
                    for rule in cfg.get("ingress_rule", []):
                        hostname = rule.get("hostname")
                        if hostname:
                            hostnames.add(hostname)
    return hostnames


def collect(infra_dir):
    infra_path = Path(infra_dir)
    clusters_dir = infra_path.parent / "clusters" / "home" / "infrastructure"
    ns_map = load_app_namespaces(clusters_dir)

    nodes = []
    routes = []
    seen_nodes = set()

    def add_node(kind, name, namespace, label):
        key = (kind, name, namespace)
        if key not in seen_nodes:
            seen_nodes.add(key)
            nodes.append({"kind": kind, "name": name, "namespace": namespace, "label": label})

    for chart_dir in sorted(infra_path.iterdir()):
        if not chart_dir.is_dir():
            continue

        chart_name = chart_dir.name
        namespace = ns_map.get(chart_name, chart_name)

        # Infrastructure nodes from Chart.yaml dependency names.
        # These are charts we wrap but don't write templates for.
        chart_yaml = chart_dir / "Chart.yaml"
        if chart_yaml.exists():
            for doc in load_docs(chart_yaml):
                for dep in doc.get("dependencies", []):
                    dep_name = dep.get("alias") or dep.get("name", "")
                    if dep_name:
                        add_node("Dependency", dep_name, namespace, dep_name)

        # Hand-written templates: structural resources and HTTPRoute backends
        templates = chart_dir / "templates"
        if not templates.exists():
            continue

        for yaml_file in sorted(templates.glob("*.yaml")):
            for doc in load_docs(yaml_file):
                kind = doc.get("kind", "")
                meta = doc.get("metadata", {})
                name = meta.get("name", "unknown")
                ns = meta.get("namespace", namespace)
                spec = doc.get("spec", {})

                if kind == "Gateway":
                    add_node(kind, name, ns, f"{name}\n(Gateway · 192.168.2.100)")

                elif kind == "Certificate":
                    dns = spec.get("dnsNames", [name])
                    add_node(kind, name, ns, f"{dns[0]}\n(Certificate)")

                elif kind == "ClusterIssuer":
                    add_node(kind, name, "cluster-scoped", f"{name}\n(ClusterIssuer)")

                elif kind == "Connector":
                    add_node(kind, name, ns, f"{name}\n(Connector)")

                elif kind == "CiliumLoadBalancerIPPool":
                    blocks = spec.get("blocks", [{}])
                    start = blocks[0].get("start", "?")
                    stop = blocks[0].get("stop", "?")
                    add_node(kind, name, "cluster-scoped", f"LB pool\n{start}–{stop}")

                elif kind == "HTTPRoute":
                    # Only HTTPS routes with real backends drive diagram edges.
                    parent_section = next(
                        (p.get("sectionName", "") for p in spec.get("parentRefs", [])), ""
                    )
                    if parent_section != "https":
                        continue
                    hostnames_list = spec.get("hostnames", [name])
                    for rule in spec.get("rules", []):
                        for backend in rule.get("backendRefs", []):
                            backend_name = backend["name"]
                            # Add the backend as a workload node in the same namespace
                            add_node("Workload", backend_name, ns, backend_name)
                            routes.append({
                                "hostname": hostnames_list[0],
                                "backend_name": backend_name,
                                "backend_namespace": ns,
                            })

    public_hostnames = load_public_hostnames(infra_dir)
    return nodes, routes, public_hostnames


def generate(nodes, routes, public_hostnames):
    lines = ["```mermaid", "flowchart TD"]

    by_ns = {}
    for n in nodes:
        by_ns.setdefault(n["namespace"], []).append(n)

    id_map = {}
    for n in nodes:
        nid = node_id(n["namespace"], n["name"])
        id_map[(n["name"], n["namespace"])] = nid

    gw_id = id_map.get(("homelab", "networking"))
    cfd_id = id_map.get(("cloudflared", "cloudflared"))
    connector_id = id_map.get(("homelab-subnet-router", "tailscale"))

    public_routes = [r for r in routes if r["hostname"] in public_hostnames]

    lines.append('    subgraph external["External"]')
    if public_routes:
        lines.append('        internet["Internet"]')
    lines.append('        lan["LAN (192.168.2.x)"]')
    lines.append('        ts_net["Tailscale Network"]')
    lines.append("    end")

    KNOWN_NS_ORDER = [
        "networking", "argocd", "cloudflared", "external-dns-internal",
        "cert-manager", "sealed-secrets", "tailscale", "longhorn-system",
        "monitoring", "cluster-scoped",
    ]

    def ns_order(ns):
        return KNOWN_NS_ORDER.index(ns) if ns in KNOWN_NS_ORDER else len(KNOWN_NS_ORDER)

    for ns in sorted(by_ns, key=ns_order):
        ns_label = ns.replace("-", "‑")
        lines.append(f'    subgraph {node_id(ns, "ns")}["{ns_label}"]')
        for n in by_ns[ns]:
            nid = node_id(n["namespace"], n["name"])
            label = n["label"].replace("\n", " · ")
            lines.append(f'        {nid}["{label}"]')
        lines.append("    end")

    if gw_id:
        lines.append(f"    lan --> {gw_id}")

    if public_routes and cfd_id and gw_id:
        lines.append(f"    internet --> {cfd_id}")
        lines.append(f"    {cfd_id} --> {gw_id}")

    if connector_id:
        lines.append(f"    ts_net --> {connector_id}")

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
