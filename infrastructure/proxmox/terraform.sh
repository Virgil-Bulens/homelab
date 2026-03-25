#!/usr/bin/env bash
# Run Terraform for the Proxmox layer, pulling secrets from the encrypted secrets repo.
#
# Usage:
#   ./terraform.sh init
#   ./terraform.sh plan
#   ./terraform.sh apply
#   ./terraform.sh destroy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_FILE="${WORKSPACE_DIR:-/workspaces/workspace}/secrets/homelab/proxmox.tfvars.gpg"

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "ERROR: secrets file not found: $SECRETS_FILE" >&2
  exit 1
fi

# Decrypt secrets into a temp file, clean up on exit
TMPFILE="$(mktemp)"
trap 'shred -u "$TMPFILE" 2>/dev/null || rm -f "$TMPFILE"' EXIT

gpg --quiet --decrypt --output "$TMPFILE" "$SECRETS_FILE"

terraform -chdir="$SCRIPT_DIR" "$@" -var-file="$TMPFILE"
