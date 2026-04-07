#!/usr/bin/env python3
"""
configure-flows.py — Configure Authentik authentication flows via API.

Commands:
  --create-flows   Build the homelab-passwordless-login flow (idempotent).
                   Does NOT activate it. Run this first, then enroll your passkey.
  --swap-flow      Replace the default authentication flow with the passwordless one.
                   Only run AFTER enrolling a passkey and verifying it works.
  --status         Print current state: flow exists? default flow set to which slug?

Requires:
  AUTHENTIK_URL   Base URL of Authentik (e.g. https://authentik.virg.be)
  AUTHENTIK_TOKEN API token with admin access

Flow design (homelab-passwordless-login):
  1. IdentificationStage  — email only (no password field)
  2. AuthenticatorValidateStage — webauthn primary, totp + static as fallback
     not_configured_action=deny (users without any MFA device cannot proceed)
  3. UserLoginStage (reuse existing default-authentication-login)

WARNING: Never run --swap-flow before:
  1. Creating the flow with --create-flows
  2. Enrolling a passkey for your account
  3. Verifying login works in an incognito window
"""
import os
import sys
import json
import argparse
import requests

BASE_URL = os.environ.get("AUTHENTIK_URL", "").rstrip("/")
TOKEN = os.environ.get("AUTHENTIK_TOKEN", "")

FLOW_SLUG = "homelab-passwordless-login"
FLOW_NAME = "Homelab Passwordless Login"

IDENTIFICATION_STAGE = "homelab-identification"
WEBAUTHN_STAGE = "homelab-webauthn-validation"
LOGIN_STAGE = "default-authentication-login"  # reuse existing


def api(method: str, path: str, **kwargs) -> dict:
    if not BASE_URL or not TOKEN:
        print("ERROR: AUTHENTIK_URL and AUTHENTIK_TOKEN must be set", file=sys.stderr)
        sys.exit(1)
    url = f"{BASE_URL}/api/v3{path}"
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    resp = getattr(requests, method)(url, headers=headers, **kwargs)
    if not resp.ok:
        print(f"API error {resp.status_code} {method.upper()} {path}: {resp.text}", file=sys.stderr)
        sys.exit(1)
    if resp.status_code == 204:
        return {}
    return resp.json()


def get_or_create(list_path: str, create_path: str, search_params: dict, payload: dict, label: str) -> dict:
    """Fetch existing object by search params, create if absent."""
    results = api("get", list_path, params=search_params).get("results", [])
    if results:
        obj = results[0]
        print(f"[exists]  {label}: {obj['pk']}")
        return obj
    obj = api("post", create_path, json=payload)
    print(f"[created] {label}: {obj['pk']}")
    return obj


def find_stage(name: str) -> dict:
    results = api("get", "/stages/all/", params={"name": name}).get("results", [])
    if not results:
        print(f"ERROR: stage '{name}' not found", file=sys.stderr)
        sys.exit(1)
    return results[0]


def find_flow(slug: str) -> dict | None:
    results = api("get", "/flows/instances/", params={"slug": slug}).get("results", [])
    return results[0] if results else None


def cmd_status():
    flow = find_flow(FLOW_SLUG)
    if flow:
        print(f"Flow '{FLOW_SLUG}' EXISTS: pk={flow['pk']}")
        bindings = api("get", "/flows/bindings/", params={"target": flow["pk"]}).get("results", [])
        for b in sorted(bindings, key=lambda x: x["order"]):
            print(f"  order={b['order']} stage={b['stage_obj']['name']}")
    else:
        print(f"Flow '{FLOW_SLUG}' does NOT exist yet")

    # Check what the default auth flow is
    brands = api("get", "/core/brands/", params={"default": "true"}).get("results", [])
    if brands:
        brand = brands[0]
        auth_flow = brand.get("flow_authentication")
        print(f"\nDefault brand auth flow: {auth_flow}")


def cmd_create_flows():
    # 1. Identification stage — email only, no password
    id_stage = get_or_create(
        "/stages/identification/", "/stages/identification/",
        {"name": IDENTIFICATION_STAGE},
        {
            "name": IDENTIFICATION_STAGE,
            "user_fields": ["email"],
            "show_matched_user": False,
            # No password_stage — passwordless
            "password_stage": None,
        },
        f"IdentificationStage '{IDENTIFICATION_STAGE}'"
    )

    # 2. WebAuthn + fallback (totp, static) validation stage
    # not_configured_action=deny means users with no device enrolled are blocked
    wa_stage = get_or_create(
        "/stages/authenticator/validate/", "/stages/authenticator/validate/",
        {"name": WEBAUTHN_STAGE},
        {
            "name": WEBAUTHN_STAGE,
            "device_classes": ["webauthn", "totp", "static"],
            "not_configured_action": "deny",
            "webauthn_user_verification": "required",
            "last_auth_threshold": "seconds=0",
            "configuration_stages": [],
        },
        f"AuthenticatorValidateStage '{WEBAUTHN_STAGE}'"
    )

    # 3. Login stage — reuse existing
    login_stage = find_stage(LOGIN_STAGE)
    print(f"[exists]  UserLoginStage '{LOGIN_STAGE}': {login_stage['pk']}")

    # 4. Flow
    flow = get_or_create(
        "/flows/instances/", "/flows/instances/",
        {"slug": FLOW_SLUG},
        {
            "name": FLOW_NAME,
            "slug": FLOW_SLUG,
            "designation": "authentication",
            "title": "Sign in",
            "authentication": "none",
        },
        f"Flow '{FLOW_SLUG}'"
    )
    flow_pk = flow["pk"]

    # 5. Stage bindings
    for order, stage in [(10, id_stage), (20, wa_stage), (100, login_stage)]:
        get_or_create(
            "/flows/bindings/", "/flows/bindings/",
            {"target": flow_pk, "stage": stage["pk"]},
            {
                "target": flow_pk,
                "stage": stage["pk"],
                "order": order,
                "evaluate_on_plan": True,
                "re_evaluate_policies": False,
                "invalid_response_action": "retry",
            },
            f"Binding order={order} stage={stage['name']}"
        )

    print(f"\nFlow '{FLOW_SLUG}' is ready.")
    print("Next steps:")
    print("  1. Log in to Authentik UI → go to your user settings")
    print("  2. Enroll a passkey (WebAuthn) under 'MFA Devices'")
    print("  3. Test login using the flow directly:")
    print(f"     {BASE_URL}/if/flow/{FLOW_SLUG}/")
    print("  4. Only after verifying it works: run --swap-flow")


def cmd_swap_flow():
    flow = find_flow(FLOW_SLUG)
    if not flow:
        print(f"ERROR: flow '{FLOW_SLUG}' not found — run --create-flows first", file=sys.stderr)
        sys.exit(1)

    brands = api("get", "/core/brands/", params={"default": "true"}).get("results", [])
    if not brands:
        print("ERROR: no default brand found", file=sys.stderr)
        sys.exit(1)

    brand = brands[0]
    current = brand.get("flow_authentication")
    if current == flow["pk"]:
        print(f"Default brand already uses '{FLOW_SLUG}' — nothing to do")
        return

    print(f"Current auth flow: {current}")
    print(f"Swapping to: {flow['pk']} ({FLOW_SLUG})")

    # PATCH the brand — only update the auth flow field
    api("patch", f"/core/brands/{brand['brand_uuid']}/", json={"flow_authentication": flow["pk"]})
    print("Done. Default authentication flow updated.")
    print("Verify: open a new incognito window and confirm login still works.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create-flows", action="store_true")
    group.add_argument("--swap-flow", action="store_true")
    group.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.create_flows:
        cmd_create_flows()
    elif args.swap_flow:
        cmd_swap_flow()


if __name__ == "__main__":
    main()
