```mermaid
flowchart TD
    subgraph external["External"]
        lan["LAN (192.168.2.x)"]
        ts_net["Tailscale Network"]
    end
    subgraph networking__ns["networking"]
        networking__virg_be_wildcard["virg.be\n(Certificate)"]
        networking__homelab["homelab\n(Gateway · 192.168.2.100)"]
    end
    subgraph argocd__ns["argocd"]
        argocd__argocd_server["argocd-server"]
    end
    subgraph cloudflared__ns["cloudflared"]
        cloudflared__cloudflared["cloudflared"]
    end
    subgraph external_dns_internal__ns["external‑dns‑internal"]
        external_dns_internal__external_dns["external-dns\n(UniFi webhook)"]
    end
    subgraph cert_manager__ns["cert‑manager"]
        cert_manager__cert_manager["cert-manager"]
    end
    subgraph sealed_secrets__ns["sealed‑secrets"]
        sealed_secrets__sealed_secrets["sealed-secrets"]
    end
    subgraph tailscale__ns["tailscale"]
        tailscale__operator["tailscale-operator"]
        tailscale__homelab_subnet_router["homelab-subnet-router\n(Connector)"]
    end
    subgraph cluster_scoped__ns["cluster‑scoped"]
        cluster_scoped__letsencrypt_staging["letsencrypt-staging\n(ClusterIssuer)"]
        cluster_scoped__letsencrypt_prod["letsencrypt-prod\n(ClusterIssuer)"]
        cluster_scoped__homelab_pool["LB pool\n192.168.2.100–192.168.2.200"]
    end
    lan --> networking__homelab
    ts_net --> tailscale__homelab_subnet_router
    networking__homelab -->|"argocd.virg.be"| argocd__argocd_server
```
