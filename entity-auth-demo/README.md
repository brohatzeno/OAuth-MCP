# entity.co auth demo

This folder contains the OAuth authorization server, protected MCP server, HTTPS harness, and local helper scripts for the entity.co connector demo.

Use the root [README.md](../README.md) for complete setup instructions. The short version from the repo root is:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./entity-auth-demo/scripts/start-mcp-stack.sh
```

Important paths:

```text
auth_server/index.py       mock OAuth server
mcp_server/index.py        protected MCP server
scripts/start-mcp-stack.sh full local stack launcher
https-harness.py           local HTTPS proxy for Claude connector testing
.env                       local OAuth client, JWT, and employee config
```

Default connector URL:

```text
https://localhost:3443/mcp
```
