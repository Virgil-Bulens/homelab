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

## Bootstrap instructions

### Prerequisites

- Proxmox host reachable at `192.168.2.x`
- SSH key in `~/.ssh/` with access to all nodes
- `PROXMOX_USERNAME` and `PROXMOX_PASSWORD` env vars set (for Terraform)

### 1. Provision infrastructure

```bash
cd infrastructure/proxmox
terraform init
terraform apply
```

### 2. Install k3s (via Ansible)

Ansible uses a dynamic inventory sourced from Terraform state — no manual IP management needed.

```bash
cd ansible
ansible-playbook playbooks/k3s.yml
```

Nodes will register but show `NotReady` — that's expected until Cilium is installed.

### 3. Fetch kubeconfig

k3s places its kubeconfig on the control plane at `/etc/rancher/k3s/k3s.yaml`. Copy it locally:

```bash
mkdir -p ~/.kube
ssh admin@192.168.2.10 "sudo cp /etc/rancher/k3s/k3s.yaml /tmp/k3s.yaml && sudo chmod 644 /tmp/k3s.yaml"
scp admin@192.168.2.10:/tmp/k3s.yaml ~/.kube/config
sed -i 's/127.0.0.1/192.168.2.10/g' ~/.kube/config
chmod 600 ~/.kube/config
```

Verify: `kubectl get nodes` — all nodes should show `NotReady`.

### 4. Install Cilium (CNI bootstrap)

Cilium must be installed directly — it cannot be managed by ArgoCD because the cluster network must exist before ArgoCD can run.

Install the Cilium CLI if not present:

```bash
CILIUM_CLI_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/cilium-cli/main/stable.txt)
curl -sL "https://github.com/cilium/cilium-cli/releases/download/${CILIUM_CLI_VERSION}/cilium-linux-amd64.tar.gz" -o /tmp/cilium.tar.gz
sudo tar xzvf /tmp/cilium.tar.gz -C /usr/local/bin
```

Install Cilium into the cluster:

```bash
cilium install --version 1.19.1 \
  --set cluster.name=homelab \
  --set ipam.mode=kubernetes \
  --set kubeProxyReplacement=true \
  --set k8sServiceHost=192.168.2.10 \
  --set k8sServicePort=6443
```

> **Note:** `k8sServiceHost` and `k8sServicePort` are required. Without them, Cilium's init container tries to reach the API server via the service IP (`10.43.0.1`), which doesn't exist yet — classic chicken-and-egg with `kubeProxyReplacement=true`.

Wait for Cilium to become healthy:

```bash
cilium status --wait
```

Verify all nodes are `Ready`:

```bash
kubectl get nodes
```

### 5. Bootstrap ArgoCD

Install ArgoCD into the cluster directly via Helm — this is the last manual install step:

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
helm install argocd argo/argo-cd \
  --namespace argocd \
  --create-namespace \
  --version 7.7.0 \
  --set server.insecure=true
```

Wait for ArgoCD to be ready:

```bash
kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=120s
```

Apply the root Application — this is the single manual `kubectl apply` that hands control to ArgoCD:

```bash
kubectl apply -f bootstrap/root-application.yaml
```

ArgoCD will discover `clusters/home/infrastructure/`, create all child Applications, and begin reconciling the cluster to match Git. From this point on, all changes go through Git.
