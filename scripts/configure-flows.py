#!/usr/bin/env python3
"""
configure-flows.py — Configure Authentik authentication flows and policies via API.

Commands:
  --create-flows     Build the homelab-passwordless-login flow (idempotent).
                     Does NOT activate it. Run this first, then enroll your passkey.
  --swap-flow        Replace the default authentication flow with the passwordless one.
                     Only run AFTER enrolling a passkey and verifying it works.
  --create-policies  Create the three conditional access expression policies (idempotent).
                     Requires GeoIP DB to be loaded (can_geo_ip in /api/v3/root/config/).
  --bind-policies    Bind the policies to homelab-passwordless-login flow.
                     Idempotent. Policies apply to ALL authentications — test first.
  --status           Print current state: flow exists? default flow? policies bound?

Requires:
  AUTHENTIK_URL   Base URL of Authentik (e.g. https://authentik.virg.be)
  AUTHENTIK_TOKEN API token with admin access

Flow design (homelab-passwordless-login):
  1. IdentificationStage  — email only (no password field)
  2. AuthenticatorValidateStage — webauthn primary, totp + static as fallback
     not_configured_action=deny (users without any MFA device cannot proceed)
  3. UserLoginStage (reuse existing default-authentication-login)

Conditional access policies (bound to flow, evaluated before stages):
  order 0 — Belgium-only GeoIP: non-BE source IPs → soft block (generic error)
  order 1 — Bad IP/Tor reputation: score < -5 → soft block
  order 2 — LAN detection: sets ak_message context var, always passes

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


POLICY_BELGIUM = "homelab-geoip-belgium"
POLICY_REPUTATION = "homelab-reputation-block"
POLICY_LAN = "homelab-lan-detection"

# Belgium ISO country code
_BELGIUM_EXPR = """\
from authentik.events.context_processors.mmdb import CONTEXT_KEY_CITY
city = request.context.get(CONTEXT_KEY_CITY)
if city is None:
    # No GeoIP data — fail open (don't block unknown IPs)
    return True
country = city.get("country", {}).get("iso_code", "")
if country != "BE":
    ak_message("Access restricted to Belgium.")
    return False
return True
"""

_LAN_EXPR = """\
import ipaddress
try:
    ip = ipaddress.ip_address(request.http_request.META.get("REMOTE_ADDR", ""))
    context["is_lan"] = ip.is_private
except Exception:
    context["is_lan"] = False
return True
"""


def cmd_create_policies():
    # Check GeoIP available
    cfg = api("get", "/root/config/")
    if "can_geo_ip" not in cfg.get("capabilities", []):
        print("ERROR: GeoIP not available in this Authentik instance", file=sys.stderr)
        sys.exit(1)
    print("[ok] GeoIP available")

    # Belgium-only expression policy
    get_or_create(
        "/policies/expression/", "/policies/expression/",
        {"name": POLICY_BELGIUM},
        {
            "name": POLICY_BELGIUM,
            "execution_logging": False,
            "expression": _BELGIUM_EXPR,
        },
        f"ExpressionPolicy '{POLICY_BELGIUM}'"
    )

    # Reputation policy (bad IP / Tor)
    get_or_create(
        "/policies/reputation/", "/policies/reputation/",
        {"name": POLICY_REPUTATION},
        {
            "name": POLICY_REPUTATION,
            "execution_logging": False,
            # Block IPs with reputation score below -5
            "threshold": -5,
            "check_ip": True,
            "check_username": False,
        },
        f"ReputationPolicy '{POLICY_REPUTATION}'"
    )

    # LAN detection expression policy (always passes, sets context)
    get_or_create(
        "/policies/expression/", "/policies/expression/",
        {"name": POLICY_LAN},
        {
            "name": POLICY_LAN,
            "execution_logging": False,
            "expression": _LAN_EXPR,
        },
        f"ExpressionPolicy '{POLICY_LAN}'"
    )

    print("\nPolicies created. Run --bind-policies to attach them to the login flow.")


def cmd_bind_policies():
    flow = find_flow(FLOW_SLUG)
    if not flow:
        print(f"ERROR: flow '{FLOW_SLUG}' not found — run --create-flows first", file=sys.stderr)
        sys.exit(1)

    # Policies are bound to FlowStageBindings (each is a PolicyBindingModel).
    # Bind to the identification stage binding (order=10) — runs before any stage.
    stage_bindings = api("get", "/flows/bindings/", params={"target": flow["pk"]}).get("results", [])
    id_binding = next((b for b in stage_bindings if b["order"] == 10), None)
    if not id_binding:
        print("ERROR: identification stage binding (order=10) not found", file=sys.stderr)
        sys.exit(1)
    target_pk = id_binding["pk"]
    print(f"Binding policies to stage binding {target_pk} (order=10, {id_binding['stage_obj']['name']})")

    policy_map = [
        (0, "/policies/expression/", POLICY_BELGIUM),
        (1, "/policies/reputation/", POLICY_REPUTATION),
        (2, "/policies/expression/", POLICY_LAN),
    ]

    for order, list_path, policy_name in policy_map:
        results = api("get", list_path, params={"name": policy_name}).get("results", [])
        if not results:
            print(f"ERROR: policy '{policy_name}' not found — run --create-policies first", file=sys.stderr)
            sys.exit(1)
        policy = results[0]

        # Can't filter /policies/bindings/ by FlowStageBinding target — search by policy pk
        existing = api("get", "/policies/bindings/", params={"policy": policy["pk"]}).get("results", [])
        already = next((b for b in existing if b.get("target") == target_pk), None)
        if already:
            print(f"[exists]  PolicyBinding order={order} policy={policy_name}: {already['pk']}")
        else:
            payload = {
                "target": target_pk,
                "policy": policy["pk"],
                "order": order,
                "enabled": True,
                "timeout": 30,
                "failure_result": True,
            }
            obj = api("post", "/policies/bindings/", json=payload)
            print(f"[created] PolicyBinding order={order} policy={policy_name}: {obj['pk']}")

    print("\nPolicies bound. Verify:")
    print("  - Login from BE IP still works")
    print("  - Check Authentik event log for policy execution events")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create-flows", action="store_true")
    group.add_argument("--swap-flow", action="store_true")
    group.add_argument("--create-policies", action="store_true")
    group.add_argument("--bind-policies", action="store_true")
    group.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.create_flows:
        cmd_create_flows()
    elif args.swap_flow:
        cmd_swap_flow()
    elif args.create_policies:
        cmd_create_policies()
    elif args.bind_policies:
        cmd_bind_policies()


if __name__ == "__main__":
    main()
