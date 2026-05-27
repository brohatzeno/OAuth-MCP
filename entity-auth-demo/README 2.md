# Entity.co Auth + MCP Demo

This is a Python demo of a mock enterprise login flow for **Entity.co**.
Employees sign in with Gmail addresses, receive an OAuth-style JWT access token, and use that token to unlock Entity.co tools exposed through an MCP server.

## Folder Structure

```text
xuno-auth-demo/
├── auth-server/
│   └── index.py
├── mcp-server/
│   └── index.py
├── login.py
├── .env
├── .env.example
├── requirements.txt
└── README.md
```

All demo credentials live in `.env`. The `.env.example` file shows the expected shape. For Claude's connector flow, you do not run `login.py` first; Claude starts OAuth when it reaches the protected MCP endpoint.

## Demo Employees

Employee emails, passwords, names, and roles are configured in `.env` with `ENTITY_EMPLOYEE_*` variables.

## Install Dependencies

From this folder:

```bash
cd "/Users/zeno/Documents/Work/xuno/codes/OAuth Backend POC/xuno-auth-demo"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If `.env` does not exist yet, create it from the example and keep your real local values there:

```bash
cp .env.example .env
```

For Claude's custom connector OAuth fields, use these values from `.env`:

```text
OAuth Client ID: ENTITY_OAUTH_CLIENT_ID
OAuth Client Secret: ENTITY_OAUTH_CLIENT_SECRET
```

## Start the Auth Backend

```bash
source .venv/bin/activate
python auth-server/index.py
```

The mock Entity.co OAuth server runs at:

```text
http://localhost:3000
```

Useful check:

```bash
curl http://localhost:3000/health
```

## Optional Local Login

```bash
source .venv/bin/activate
python login.py
```

This optional script opens the Entity.co login page, receives the OAuth authorization code on `http://localhost:3002/callback`, redeems the code for a JWT access token, and saves the token to `.env` as `ENTITY_ACCESS_TOKEN=...`.

## Start the MCP Server

```bash
source .venv/bin/activate
python mcp-server/index.py
```

The MCP server runs at:

```text
http://localhost:3001/mcp
```

Health check:

```bash
curl http://localhost:3001/health
```

If a request has no valid bearer token, `/mcp` returns an OAuth challenge. Claude uses that challenge to send the user to the Entity.co login page.

For local Desktop-only testing, `.env` can enable:

```text
ENTITY_ALLOW_UNAUTHENTICATED_LOCAL=true
```

That bypass is accepted only for loopback requests forwarded by the local HTTPS harness. Keep it disabled for public tunnels or deployed connector testing.

## Claude Custom Connector Local HTTPS Harness

To start the full local MCP connection stack in one terminal:

```bash
chmod +x start-mcp-stack.sh
./start-mcp-stack.sh
```

This starts:

```text
Auth server:        http://127.0.0.1:3000
MCP server:         http://127.0.0.1:3001/mcp
HTTPS harness:      https://localhost:3443
Connector URL:      https://localhost:3443/mcp
```

Use this in Claude's connector form:

```text
Name: Entity.co Enterprise MCP
Remote MCP server URL: https://localhost:3443/mcp
OAuth Client ID: value from ENTITY_OAUTH_CLIENT_ID
OAuth Client Secret: value from ENTITY_OAUTH_CLIENT_SECRET
```

For a cloud-hosted MCP client that cannot reach your machine's localhost URL, expose the same stack through a temporary Cloudflare tunnel:

```bash
chmod +x start-mcp-cloudflare-tunnel.sh
./start-mcp-cloudflare-tunnel.sh
```

The script prints a public connector URL:

```text
https://<generated-name>.trycloudflare.com/mcp
```

## MCP Tools

```text
get_company_info   - Entity.co company details
get_employee_list  - mock employee directory
get_user_profile   - current logged-in employee
get_dummy_data     - static dummy records for end-to-end testing
```
