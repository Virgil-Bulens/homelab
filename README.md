# homelab

GitOps homelab running on Proxmox (Intel NUC i7, 64 GB RAM). Built as a learning platform for modern cloud-native practices and as a public portfolio of platform engineering work.

## Principles

- **GitOps** — all cluster state lives in this repository; no manual changes to infrastructure
- **Zero trust** — network-level and identity/auth enforced throughout
- **Observability** — metrics, logs, and alerting across the full stack
- **Documentation-first** — decisions and architecture captured alongside the code

## Infrastructure

See [infrastructure diagram](docs/infrastructure.md) — auto-generated from `infrastructure/proxmox/*.tf` on every push.

See [cluster diagram](docs/cluster.md) — auto-generated from `infrastructure/` manifests and Helm charts on every push.

## Tech stack

| Layer | Tool |
|---|---|
| Kubernetes | k3s |
| GitOps | ArgoCD |
| CNI | Cilium |
| Remote access | Tailscale |
| Ingress | Gateway API (via Cilium) |
| Public ingress | Cloudflare Tunnel |
| Certificates | cert-manager + Let's Encrypt (DNS-01 via Cloudflare) |
| DNS | Split-horizon: external-dns (UniFi, internal LAN) + external-dns (Cloudflare, public internet) |
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
infrastructure/       # Helm values, Kubernetes manifests, and Terraform per component
  proxmox/            # Terraform — Proxmox VMs + Ansible inventory
  unifi/              # Terraform — UniFi DNS records and DHCP reservations
  tailscale-acl/      # Tailscale ACL (HuJSON) — applied to tailnet via CI
  argocd/
  cilium/             # Bootstrap reference values (helm upgrade, not ArgoCD)
  cilium-config/      # ArgoCD-managed Cilium CRD instances (LoadBalancer IP pool)
  cert-manager/
  gateway/            # networking namespace, wildcard Certificate, Gateway resource
  external-dns-internal/  # external-dns → UniFi (internal LAN DNS)
  external-dns-external/  # external-dns → Cloudflare (public internet DNS)
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
5. Gateway API CRDs (bootstrap) + Cilium upgrade + cert-manager + Gateway + split-horizon external-dns (UniFi internal + Cloudflare external) + Cloudflare Tunnel
6. Longhorn (persistent storage — required before Observability and app deployments)
7. Observability stack (kube-prometheus-stack + Loki)
8. Authentik (SSO for all services)
9. Self-hosted apps

## Bootstrap instructions

### Prerequisites

- Proxmox host reachable at `192.168.2.x`
- SSH key in `~/.ssh/` with access to all nodes
- Terraform variables available (see `infrastructure/proxmox/terraform.tfvars.example` and `infrastructure/unifi/terraform.tfvars.example`)

### 1. Provision infrastructure

Proxmox VMs and UniFi DNS/DHCP records are managed in separate Terraform root modules. In CI, both run automatically on push. To run locally:

```bash
cd infrastructure/proxmox
terraform init
terraform apply

cd ../unifi
terraform init
terraform apply -parallelism=1  # required: provider has a concurrency limitation
```

### 2. Install k3s (via Ansible)

Ansible uses a dynamic inventory sourced from Terraform state — no manual IP management needed.

```bash
cd ansible
ansible-playbook playbooks/k3s.yml
```

Nodes will register but show `NotReady` — that's expected until Cilium is installed.

### 3. Install Longhorn prerequisites

Longhorn requires `open-iscsi` (block storage) and `nfs-common` on every cluster node. Run this before ArgoCD deploys Longhorn:

```bash
cd ansible
ansible-playbook playbooks/longhorn-prereqs.yml
```

### 4. Fetch kubeconfig

k3s places its kubeconfig on the control plane at `/etc/rancher/k3s/k3s.yaml`. Copy it locally:

```bash
mkdir -p ~/.kube
ssh admin@192.168.2.10 "sudo cp /etc/rancher/k3s/k3s.yaml /tmp/k3s.yaml && sudo chmod 644 /tmp/k3s.yaml"
scp admin@192.168.2.10:/tmp/k3s.yaml ~/.kube/config
sed -i 's/127.0.0.1/192.168.2.10/g' ~/.kube/config
chmod 600 ~/.kube/config
```

Verify: `kubectl get nodes` — all nodes should show `NotReady`.

### 5. Install Cilium (CNI bootstrap)

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

### 6. Bootstrap ArgoCD

Install ArgoCD into the cluster directly via Helm — this is the last manual install step:

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
helm install argocd argo/argo-cd \
  --namespace argocd \
  --create-namespace \
  --version 7.7.0
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

### 7. Enable Gateway API

Gateway API CRDs and the Cilium upgrade are bootstrap steps — applied directly like Cilium and ArgoCD.

Install Gateway API CRDs (v1.2.1 — matches Cilium 1.19.x):

```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.1/standard-install.yaml
```

Upgrade Cilium to enable the Gateway API controller:

```bash
helm repo add cilium https://helm.cilium.io/
helm upgrade cilium cilium/cilium -n kube-system -f infrastructure/cilium/values.yaml
```

ArgoCD then manages the `CiliumLoadBalancerIPPool`, `networking` namespace, wildcard `Certificate`, and `Gateway` resources via the `cilium-config` and `gateway` Applications.
