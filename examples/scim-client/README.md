# SCIM 2.0 Client — Keycloak Example

Example Python client that provisions users and groups via the SCIM 2.0 API
exposed by Red Hat Build of Keycloak (realm **scim**, feature `scim-api`).

## Prerequisites

| Component | Requirement |
|-----------|-------------|
| Keycloak  | `scim-api` feature enabled (baked into the container image) |
| Realm     | `scim` realm exists with SCIM protocol enabled |
| Client    | A **confidential** client with service-account enabled and `realm-admin` role |
| Python    | 3.10+ |

## Keycloak Client Setup

In the **scim** realm admin console:

1. **Create client** `scim-client` (Client type: OpenID Connect)
2. Enable **Client authentication** (confidential)
3. Enable **Service account roles**
4. Disable all other authentication flows (Standard flow, etc.)
5. Under **Service account roles**, assign:
   - `realm-management` → `realm-admin` (or narrower scim-specific roles if available)
6. Copy the **Client secret** from the Credentials tab

## Usage

```bash
cd examples/scim-client
pip install -r requirements.txt

export KEYCLOAK_URL=https://keycloak.apps.sno.myocp.net/auth
export SCIM_REALM=scim
export CLIENT_ID=scim-client
export CLIENT_SECRET=<your-client-secret>

python scim_client.py
```

The demo script will:
1. List existing SCIM users
2. Create a test user (`scim.test`)
3. Read the user back
4. Update the user's name
5. Create a group with the user as member
6. List groups
7. Clean up (delete user and group)

## Using Individual Functions

```python
from scim_client import get_access_token, list_users, create_user

token = get_access_token()

# List users with a SCIM filter
users = list_users(token, filter_expr='userName eq "admin"')

# Create a user
user = create_user(token, "jean.dupont", "Jean", "Dupont", "jean.dupont@example.com")
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KEYCLOAK_URL` | `https://keycloak.apps.sno.myocp.net/auth` | Keycloak base URL (with `/auth` path) |
| `SCIM_REALM` | `scim` | Target realm |
| `CLIENT_ID` | `scim-client` | OAuth2 client ID |
| `CLIENT_SECRET` | *(required)* | OAuth2 client secret |

## SCIM Endpoints Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/realms/{realm}/scim/v2/Users` | List / search users |
| `POST` | `/realms/{realm}/scim/v2/Users` | Create user |
| `GET` | `/realms/{realm}/scim/v2/Users/{id}` | Get user |
| `PUT` | `/realms/{realm}/scim/v2/Users/{id}` | Replace user |
| `DELETE` | `/realms/{realm}/scim/v2/Users/{id}` | Delete user |
| `GET` | `/realms/{realm}/scim/v2/Groups` | List groups |
| `POST` | `/realms/{realm}/scim/v2/Groups` | Create group |
| `DELETE` | `/realms/{realm}/scim/v2/Groups/{id}` | Delete group |

All paths are relative to `KEYCLOAK_URL` (e.g. `https://keycloak.apps.sno.myocp.net/auth`).
