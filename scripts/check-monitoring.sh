#!/usr/bin/env bash
# check-monitoring.sh — health snapshot of the monitoring stack
# Usage: ./scripts/check-monitoring.sh
set -euo pipefail

RED='\033[0;31m' YLW='\033[0;33m' GRN='\033[0;32m' DIM='\033[2m' RST='\033[0m'
ok()   { echo -e "  ${GRN}OK${RST}   $*"; }
warn() { echo -e "  ${YLW}WARN${RST} $*"; }
fail() { echo -e "  ${RED}FAIL${RST} $*"; }
hdr()  { echo -e "\n${DIM}── $* ──${RST}"; }

# ── ArgoCD sync status ────────────────────────────────────────────────────────
hdr "ArgoCD applications"
for app in argocd monitoring longhorn; do
  status=$(kubectl get application "$app" -n argocd \
    -o jsonpath='{.status.sync.status}/{.status.health.status}' 2>/dev/null || echo "NotFound/Unknown")
  sync=${status%%/*}; health=${status##*/}
  if [[ "$sync" == "Synced" && "$health" == "Healthy" ]]; then
    ok "$app  ($sync / $health)"
  else
    fail "$app  ($sync / $health)"
  fi
done

# ── Pod status ───────────────────────────────────────────────────────────────
hdr "Pods (monitoring)"
not_running=$(kubectl get pods -n monitoring --no-headers 2>&1 \
  | grep -v " Running \| Completed " || true)
running_count=$(kubectl get pods -n monitoring --no-headers 2>&1 | grep -c " Running " || true)
if [[ -z "$not_running" ]]; then
  ok "$running_count pods Running"
else
  warn "$running_count Running, non-Running pods:"
  echo "$not_running" | sed 's/^/       /'
fi

# ── PVC status ───────────────────────────────────────────────────────────────
hdr "PVCs (monitoring)"
kubectl get pvc -n monitoring --no-headers 2>&1 | while read -r line; do
  name=$(echo "$line" | awk '{print $1}')
  status=$(echo "$line" | awk '{print $2}')
  cap=$(echo "$line" | awk '{print $4}')
  sc=$(echo "$line" | awk '{print $6}')
  if [[ "$status" == "Bound" ]]; then
    ok "$name  ($cap on $sc)"
  else
    fail "$name  status=$status"
  fi
done

# ── Prometheus targets ────────────────────────────────────────────────────────
hdr "Prometheus targets"
result=$(kubectl get --raw \
  /api/v1/namespaces/monitoring/services/prometheus-operated:9090/proxy/api/v1/targets 2>&1)
total=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['data']['activeTargets']))")
down=$(echo "$result"  | python3 -c "
import sys,json
d=json.load(sys.stdin)
bad=[t for t in d['data']['activeTargets'] if t['health']!='up']
print(len(bad))
for t in bad:
  print(f\"  DOWN: {t['labels'].get('job','?')} / {t['labels'].get('instance','?')} — {t.get('lastError','')}\")
")
down_count=$(echo "$down" | head -1)
if [[ "$down_count" == "0" ]]; then
  ok "$total/$(( total )) targets up"
else
  fail "$down_count targets down (total $total)"
  echo "$down" | tail -n +2 | sed 's/^/       /'
fi

# ── Firing alerts ─────────────────────────────────────────────────────────────
hdr "Prometheus alerts"
kubectl get --raw \
  /api/v1/namespaces/monitoring/services/prometheus-operated:9090/proxy/api/v1/alerts 2>&1 \
| python3 -c "
import sys, json, os
RED='\033[0;31m'; YLW='\033[0;33m'; GRN='\033[0;32m'; RST='\033[0m'
data = json.load(sys.stdin)
alerts = data['data']['alerts']
firing  = [a for a in alerts if a['state'] == 'firing'  and a['labels'].get('severity') != 'none']
pending = [a for a in alerts if a['state'] == 'pending']
if not firing and not pending:
    print(f'  {GRN}OK{RST}   no alerts firing')
else:
    for a in firing:
        name = a['labels'].get('alertname','?')
        sev  = a['labels'].get('severity','?')
        desc = a['annotations'].get('description','') or a['annotations'].get('summary','')
        print(f'  {RED}FIRE{RST} [{sev}] {name}')
        if desc: print(f'       {desc[:120]}')
    for a in pending:
        name = a['labels'].get('alertname','?')
        sev  = a['labels'].get('severity','?')
        print(f'  {YLW}PEND{RST} [{sev}] {name}')
"

# ── Recent warning events ─────────────────────────────────────────────────────
hdr "Recent warning events (monitoring)"
events=$(kubectl get events -n monitoring \
  --sort-by='.lastTimestamp' --field-selector type=Warning \
  --no-headers 2>&1 | tail -5)
if [[ -z "$events" ]]; then
  ok "no warning events"
else
  echo "$events" | sed 's/^/  /'
fi

echo
