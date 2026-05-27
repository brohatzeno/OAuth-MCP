# OAuth MCP Backend POC

This repo contains a local proof of concept for OAuth authentication and MCP connector testing. It has two related backends:

- `entity_backend/`: a simple JWT-protected FastAPI API.
- `entity-auth-demo/`: a mock OAuth 2.0 authorization server plus a protected MCP server for Claude custom connector testing.

The demo uses Gmail addresses for employees and static dummy records.

## Directory Layout

```text
OAuth Backend POC/
├── entity_backend/
│   ├── app.py                  # JWT-protected FastAPI API
│   ├── auth.py                 # JWT helpers and email-domain validation
│   ├── database.py             # Mock users, dummy data, token blacklist
│   └── models.py               # Pydantic request/response schemas
├── entity-auth-demo/
│   ├── auth_server/index.py    # Mock OAuth authorization server
│   ├── mcp_server/index.py     # Protected MCP server and tools
│   ├── scripts/                # Local stack launchers
│   ├── certs/                  # Generated localhost TLS certs, ignored by git
│   ├── https-harness.py        # Local HTTPS reverse proxy
│   ├── login.py                # Optional browser login helper
│   ├── .env                    # Local OAuth/MCP config, ignored by git
│   └── .env.example
├── docs/system.md              # System notes and flow reference
├── requirements.txt            # Shared Python dependencies
├── .env                        # Root API config, ignored by git
└── .env.example
```

## What The System Does

The root API demonstrates regular JWT authentication for an internal backend:

1. A user logs in with a `@gmail.com` demo account.
2. The API validates the email domain and password against in-memory users.
3. The API issues a JWT access token.
4. Protected endpoints accept `Authorization: Bearer <token>`.
5. `/dummy-data` returns static test records.

The OAuth/MCP demo demonstrates an authenticated remote MCP connector:

1. Claude connects to `https://localhost:3443/mcp`.
2. The MCP server returns an OAuth challenge if the request has no valid bearer token.
3. Claude discovers OAuth metadata through the local HTTPS harness.
4. The user signs in on the entity.co login page.
5. Claude redeems the authorization code for a JWT.
6. Claude retries `/mcp` with the bearer token.
7. The MCP server verifies the token with `/userinfo`.
8. Authenticated MCP tools become available.

## Requirements

- Python 3.11 or newer
- `openssl`, only needed when generating the localhost TLS certificate
- `cloudflared`, only needed for temporary public tunnel testing

## Install

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create local config files if needed:

```bash
cp .env.example .env
cp entity-auth-demo/.env.example entity-auth-demo/.env
```

Real `.env` files are intentionally ignored by git. Copy the examples, then edit secrets and employee values before starting services.

## Configuration

Root API config lives in `.env`:

```text
SERVER_HOST=127.0.0.1
SERVER_PORT=8000
COMPANY_DOMAIN=gmail.com
BACKEND_USER_1_EMAIL=admin@gmail.com
BACKEND_USER_1_PASSWORD=password123
```

OAuth/MCP config lives in `entity-auth-demo/.env`:

```text
AUTH_PORT=3000
MCP_PORT=3001
ENTITY_AUTH_SERVER_URL=http://localhost:3000
ENTITY_PUBLIC_AUTH_ISSUER=https://localhost:3443
ENTITY_PUBLIC_MCP_URL=https://localhost:3443/mcp
ENTITY_JWT_SECRET=...
ENTITY_OAUTH_CLIENT_ID=...
ENTITY_OAUTH_CLIENT_SECRET=...
ENTITY_EMPLOYEE_1_EMAIL=admin@gmail.com
ENTITY_EMPLOYEE_1_PASSWORD=password123
```

## Run The Root API

Start the backend:

```bash
source .venv/bin/activate
python -m entity_backend.app
```

Default URL:

```text
http://127.0.0.1:8000
```

Useful checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/dummy-data
```

Login example:

```bash
curl -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@gmail.com","password":"password123"}'
```

Default root API users are configured in `.env` with `BACKEND_USER_*` variables:

```text
BACKEND_USER_1_EMAIL=admin@gmail.com
BACKEND_USER_1_PASSWORD=password123
BACKEND_USER_1_FULL_NAME=Admin User
BACKEND_USER_1_DEPARTMENT=Engineering
```

Add more users by incrementing the number, for example `BACKEND_USER_2_EMAIL`,
`BACKEND_USER_2_PASSWORD`, `BACKEND_USER_2_FULL_NAME`, and
`BACKEND_USER_2_DEPARTMENT`.

## Run The OAuth + MCP Stack

Start all local connector services in one terminal:

```bash
source .venv/bin/activate
./entity-auth-demo/scripts/start-mcp-stack.sh
```

The script starts:

```text
Auth server:        http://127.0.0.1:3000
MCP server:         http://127.0.0.1:3001/mcp
HTTPS harness:      https://localhost:3443
Connector URL:      https://localhost:3443/mcp
```

Use these values in Claude's custom connector form:

```text
Name: entity.co Enterprise MCP
Remote MCP server URL: https://localhost:3443/mcp
OAuth Client ID: value from ENTITY_OAUTH_CLIENT_ID
OAuth Client Secret: value from ENTITY_OAUTH_CLIENT_SECRET
```

The OAuth login page uses the `ENTITY_EMPLOYEE_*` values in
`entity-auth-demo/.env`. By default, the first demo login is
`admin@gmail.com` with password `password123`.

For a public temporary tunnel:

```bash
source .venv/bin/activate
./entity-auth-demo/scripts/start-mcp-cloudflare-tunnel.sh
```

The tunnel script prints a public `https://<name>.trycloudflare.com/mcp` connector URL.

## Run Services Manually

Terminal 1, auth server:

```bash
source .venv/bin/activate
cd entity-auth-demo
python auth_server/index.py
```

Terminal 2, MCP server:

```bash
source .venv/bin/activate
cd entity-auth-demo
python mcp_server/index.py
```

Terminal 3, HTTPS harness:

```bash
source .venv/bin/activate
./entity-auth-demo/scripts/start-https-harness.sh
```

## Optional Browser Login Helper

For local token testing outside Claude:

```bash
source .venv/bin/activate
cd entity-auth-demo
python login.py
```

The script opens the entity.co login page, receives the OAuth callback on `http://localhost:3002/callback`, redeems the authorization code, and writes `ENTITY_ACCESS_TOKEN=...` to `entity-auth-demo/.env`.

## MCP Tools

Authenticated MCP clients can use:

| Tool | Description |
| --- | --- |
| `get_company_info` | Returns entity.co demo company metadata |
| `get_employee_list` | Returns employees configured in `entity-auth-demo/.env` |
| `get_user_profile` | Returns the authenticated user from the token |
| `get_dummy_data` | Returns static dummy records for smoke testing |

## API Endpoints

Root API:

| Endpoint | Method | Description |
| --- | --- | --- |
| `/` | `GET` | Health check |
| `/health` | `GET` | Detailed health status |
| `/login` | `POST` | Authenticate and receive a JWT |
| `/logout` | `POST` | Revoke the current JWT |
| `/me` | `GET` | Get the authenticated user |
| `/dummy-data` | `GET` | Return static dummy records |
| `/api/test/protected` | `GET` | Protected test endpoint |
| `/api/test/echo` | `POST` | Echo test endpoint |

OAuth server:

| Endpoint | Method | Description |
| --- | --- | --- |
| `/authorize` | `GET`/`POST` | Render login and issue authorization codes |
| `/token` | `POST` | Exchange authorization code for JWT |
| `/userinfo` | `GET` | Validate bearer token and return name/email |
| `/register` | `POST` | Dynamic client registration for OAuth clients |
| `/.well-known/openid-configuration` | `GET` | OAuth/OIDC discovery |

## Notes

- The demo is intentionally in-memory and local-first.
- JWT secrets and OAuth client secrets are local demo values only.
- Gmail is used as the accepted demo email domain.
- Dummy data is static and has no external data dependency.
- Generated logs are written to `entity-auth-demo/logs/` and are ignored by git.
