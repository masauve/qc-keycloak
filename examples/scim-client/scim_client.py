#!/usr/bin/env python3
"""
Example SCIM 2.0 client for Red Hat Build of Keycloak.

Requires:
  - The 'scim-api' feature enabled on the Keycloak server
  - A confidential client with a service account that has the 'realm-admin'
    role (or at minimum the scim-related roles) in the target realm

Usage:
  export KEYCLOAK_URL=https://keycloak.apps.sno.myocp.net/auth
  export SCIM_REALM=scim
  export CLIENT_ID=scim-client
  export CLIENT_SECRET=<your-secret>
  python scim_client.py
"""

import json
import os
import sys
from urllib.parse import urljoin

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "https://keycloak.apps.sno.myocp.net/auth")
SCIM_REALM = os.environ.get("SCIM_REALM", "scim")
CLIENT_ID = os.environ.get("CLIENT_ID", "scim-client")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")

TOKEN_URL = f"{KEYCLOAK_URL}/realms/{SCIM_REALM}/protocol/openid-connect/token"
SCIM_BASE = f"{KEYCLOAK_URL}/realms/{SCIM_REALM}/scim/v2"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def get_access_token() -> str:
    """Obtain a bearer token via the client-credentials grant."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def scim_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ---------------------------------------------------------------------------
# SCIM Users
# ---------------------------------------------------------------------------


def list_users(token: str, start_index: int = 1, count: int = 10, filter_expr: str | None = None):
    """GET /Users — list users with optional SCIM filter."""
    params = {"startIndex": start_index, "count": count}
    if filter_expr:
        params["filter"] = filter_expr
    resp = requests.get(f"{SCIM_BASE}/Users", headers=scim_headers(token), params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_user(token: str, user_id: str):
    """GET /Users/{id}"""
    resp = requests.get(f"{SCIM_BASE}/Users/{user_id}", headers=scim_headers(token), timeout=10)
    resp.raise_for_status()
    return resp.json()


def create_user(token: str, username: str, given_name: str, family_name: str, email: str, active: bool = True):
    """POST /Users — provision a new user."""
    payload = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": username,
        "name": {
            "givenName": given_name,
            "familyName": family_name,
        },
        "emails": [
            {
                "value": email,
                "primary": True,
            }
        ],
        "active": active,
    }
    resp = requests.post(f"{SCIM_BASE}/Users", headers=scim_headers(token), json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def update_user(token: str, user_id: str, given_name: str | None = None, family_name: str | None = None,
                email: str | None = None, active: bool | None = None):
    """PUT /Users/{id} — full replacement update."""
    current = get_user(token, user_id)

    if given_name is not None:
        current.setdefault("name", {})["givenName"] = given_name
    if family_name is not None:
        current.setdefault("name", {})["familyName"] = family_name
    if email is not None:
        current["emails"] = [{"value": email, "primary": True}]
    if active is not None:
        current["active"] = active

    resp = requests.put(f"{SCIM_BASE}/Users/{user_id}", headers=scim_headers(token), json=current, timeout=10)
    resp.raise_for_status()
    return resp.json()


def delete_user(token: str, user_id: str):
    """DELETE /Users/{id}"""
    resp = requests.delete(f"{SCIM_BASE}/Users/{user_id}", headers=scim_headers(token), timeout=10)
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# SCIM Groups
# ---------------------------------------------------------------------------


def list_groups(token: str, start_index: int = 1, count: int = 10):
    """GET /Groups"""
    params = {"startIndex": start_index, "count": count}
    resp = requests.get(f"{SCIM_BASE}/Groups", headers=scim_headers(token), params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def create_group(token: str, display_name: str):
    """POST /Groups — create a group."""
    payload = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
        "displayName": display_name,
    }
    resp = requests.post(f"{SCIM_BASE}/Groups", headers=scim_headers(token), json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def add_group_member(token: str, group_id: str, user_id: str):
    """PATCH /Groups/{id} — add a member via SCIM PatchOp."""
    payload = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [
            {
                "op": "add",
                "path": "members",
                "value": [{"value": user_id}],
            }
        ],
    }
    resp = requests.patch(f"{SCIM_BASE}/Groups/{group_id}", headers=scim_headers(token), json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def delete_group(token: str, group_id: str):
    """DELETE /Groups/{id}"""
    resp = requests.delete(f"{SCIM_BASE}/Groups/{group_id}", headers=scim_headers(token), timeout=10)
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------


def pp(label: str, data):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main():
    if not CLIENT_SECRET:
        print("Error: set CLIENT_SECRET (export CLIENT_SECRET=<secret>)", file=sys.stderr)
        sys.exit(1)

    token = get_access_token()
    print(f"Authenticated as client '{CLIENT_ID}' on realm '{SCIM_REALM}'")

    # 1. List existing users
    users = list_users(token)
    pp("Existing SCIM Users", users)

    # 2. Create a test user (delete leftover from a previous run if it exists)
    existing = list_users(token, filter_expr='userName eq "scim.test"')
    for u in existing.get("Resources", []):
        print(f"Removing leftover user scim.test (id={u['id']})")
        delete_user(token, u["id"])

    new_user = create_user(
        token,
        username="scim.test",
        given_name="Test",
        family_name="SCIM",
        email="scim.test@example.com",
    )
    user_id = new_user["id"]
    pp(f"Created user (id={user_id})", new_user)

    # 3. Read it back
    fetched = get_user(token, user_id)
    pp("Fetched user", fetched)

    # 4. Update the user
    updated = update_user(token, user_id, given_name="Updated")
    pp("Updated user", updated)

    # 5. Create a group, then add the user as member
    group = create_group(token, display_name="scim-demo-group")
    group_id = group["id"]
    pp(f"Created group (id={group_id})", group)

    updated_group = add_group_member(token, group_id, user_id)
    pp(f"Added user to group", updated_group)

    # 6. List groups
    groups = list_groups(token)
    pp("Groups", groups)

    # 7. Clean up
    delete_user(token, user_id)
    delete_group(token, group_id)
    print(f"\nCleaned up: deleted user {user_id} and group {group_id}")


if __name__ == "__main__":
    main()
