# entity.co OAuth + MCP Demo - Internal Team Documentation

| Field | Value |
| --- | --- |
| System | entity.co OAuth + MCP Demo |
| Purpose | Demonstrate authenticated MCP tool access |
| Auth model | Mock OAuth 2.0 authorization-code flow with JWT bearer tokens |
| Demo email domain | `gmail.com` |

## Summary

This project demonstrates how an MCP server can require company authentication before exposing tools to an AI client such as Claude Desktop.

The stack has three local services:

1. A mock entity.co OAuth 2.0 authorization server.
2. A protected entity.co MCP server.
3. A local HTTPS harness for Claude custom connector testing.

Claude connects to the MCP server through the custom connector HTTPS URL. If Claude does not yet have a valid token, the MCP server returns an OAuth challenge. Claude then opens an entity.co login page, the employee signs in with Gmail credentials from `.env`, and Claude receives an access token. Only after that token is validated does the MCP server expose company tools.

## Components

| File | Responsibility |
| --- | --- |
| `entity-auth-demo/auth_server/index.py` | Mock OAuth authorization server and entity.co login UI |
| `entity-auth-demo/mcp_server/index.py` | Protected MCP server and entity.co tools |
| `entity-auth-demo/https-harness.py` | Local HTTPS reverse proxy for connector testing |
| `entity-auth-demo/login.py` | Optional browser login helper for local token generation |
| `entity-auth-demo/.env` | Local secrets, OAuth client settings, and employee credentials |

## Environment

The OAuth/MCP demo uses these `ENTITY_*` variables:

```text
ENTITY_AUTH_SERVER_URL
ENTITY_PUBLIC_AUTH_ISSUER
ENTITY_PUBLIC_MCP_URL
ENTITY_ALLOW_UNAUTHENTICATED_LOCAL
ENTITY_JWT_SECRET
ENTITY_OAUTH_CLIENT_ID
ENTITY_OAUTH_CLIENT_SECRET
ENTITY_EMPLOYEE_* values
```

The root FastAPI backend uses:

```text
COMPANY_DOMAIN=gmail.com
```

## OAuth Flow

```text
1. Claude connects to /mcp
2. MCP returns an OAuth challenge if no valid bearer token is present
3. Claude discovers the protected resource metadata
4. Claude discovers the authorization server metadata
5. Claude redirects the user to /authorize
6. The user signs in on the entity.co login page
7. Claude redeems the authorization code at /token
8. Claude calls /mcp again with Authorization: Bearer <token>
9. MCP verifies the token with /userinfo and exposes tools
```

## OAuth Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/authorize` | Render entity.co login page |
| `POST` | `/authorize` | Validate employee credentials and redirect with a code |
| `POST` | `/token` | Redeem auth code for JWT access token |
| `GET` | `/userinfo` | Verify bearer token and return name/email |
| `GET` | `/health` | Return auth backend health |

## MCP Tools

| Tool | Purpose |
| --- | --- |
| `get_company_info` | Returns entity.co demo company details |
| `get_employee_list` | Returns the mock employee directory from `.env` |
| `get_user_profile` | Returns the currently authenticated employee |
| `get_dummy_data` | Returns static dummy records for end-to-end testing |

## Dummy Data

All previous rate-comparison data has been removed. The demo now returns neutral static records such as sample customers, invoices, and support tickets. This keeps connector testing deterministic without implying live business or financial data.

## Local Stack

Start the full local stack:

```bash
./entity-auth-demo/scripts/start-mcp-stack.sh
```

Default URLs:

```text
Auth server:        http://127.0.0.1:3000
MCP server:         http://127.0.0.1:3001/mcp
HTTPS harness:      https://localhost:3443
Connector URL:      https://localhost:3443/mcp
```

For a public temporary connector URL:

```bash
./entity-auth-demo/scripts/start-mcp-cloudflare-tunnel.sh
```
