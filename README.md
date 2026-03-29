# homelab

GitOps homelab running on Proxmox (Intel NUC i7, 64 GB RAM). Built as a learning platform for modern cloud-native practices and as a public portfolio of platform engineering work.

## Principles

- **GitOps** — all cluster state lives in this repository; no manual changes to infrastructure
- **Zero trust** — network-level and identity/auth enforced throughout
- **Observability** — metrics, logs, and alerting across the full stack
- **Documentation-first** — decisions and architecture captured alongside the code

## Infrastructure

See [infrastructure diagram](docs/infrastructure.md) — auto-generated from `infrastructure/proxmox/*.tf` on every push.

## Tech stack

| Layer | Tool |
|---|---|
| Kubernetes | k3s |
| GitOps | ArgoCD |
| CNI | Cilium |
| Remote access | Tailscale |
| Ingress | Gateway API (via Cilium) |
| Certificates | cert-manager + Let's Encrypt |
| DNS | external-dns (Unifi provider) |
| Observability | Grafana + Prometheus + Loki |
| Storage | Longhorn |
| Secrets | Sealed Secrets |
| CI | GitHub Actions |
| Identity / SSO | Authentik |

## Repository layout

```
clusters/
  home/
    infrastructure/   # ArgoCD Applications for core infrastructure
    apps/             # ArgoCD Applications for user-facing apps
infrastructure/       # Helm values and Kubernetes manifests per component
  argocd/
  cilium/
  cert-manager/
  external-dns/
  sealed-secrets/
  tailscale/
  monitoring/
  longhorn/
  authentik/
apps/                 # Manifests for self-hosted applications
docs/                 # Architecture notes and ADRs
.github/
  workflows/          # GitHub Actions CI pipelines
```

## GitOps pattern

This repo uses the ArgoCD **App of Apps** pattern. A root Application in `clusters/home/` points to the `infrastructure/` and `apps/` directories. ArgoCD reconciles all child Applications automatically.

## Build order

1. Provision VMs on Proxmox
2. Install k3s with Cilium as CNI
3. Bootstrap ArgoCD — all subsequent installs are managed via ArgoCD
4. Sealed Secrets controller + Tailscale operator
5. Gateway API + cert-manager + external-dns
6. Observability stack (kube-prometheus-stack + Loki)
7. Authentik (SSO for all services)
8. Longhorn (persistent storage)
9. Self-hosted apps
