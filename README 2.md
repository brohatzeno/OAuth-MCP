# OAuth Backend POC

Mock Entity.co authentication backends for local API and Claude custom connector testing.

## Project Structure

```text
OAuth Backend POC/
├── xuno_backend/
│   ├── app.py          # FastAPI JWT backend
│   ├── auth.py         # JWT creation and validation helpers
│   ├── database.py     # Mock users, dummy records, and token blacklist
│   └── models.py       # Pydantic request/response models
├── xuno-auth-demo/     # Full OAuth + remote MCP connector demo
├── requirements.txt
├── .env.example
└── .gitignore
```

## Root Entity.co Backend

The root backend is a simple JWT-protected mock API for `@gmail.com` users.

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Update `.env`, then start the API:

```bash
python -m xuno_backend.app
```

The API runs on `http://127.0.0.1:8000` by default.

To run it with local HTTPS, set these in `.env`:

```bash
SERVER_PORT=8443
SSL_CERT_FILE=xuno-auth-demo/certs/localhost.pem
SSL_KEY_FILE=xuno-auth-demo/certs/localhost-key.pem
```

Then start the API with the same command:

```bash
python -m xuno_backend.app
```

### Default Test Users

All demo users use `password123`.

- `admin@gmail.com`
- `qa@gmail.com`
- `finance@gmail.com`
- `marketing@gmail.com`
- `sales@gmail.com`

### API Endpoints

| Endpoint | Method | Description |
| --- | --- | --- |
| `/` | GET | Health check |
| `/health` | GET | Detailed health status |
| `/login` | POST | Authenticate and receive a JWT |
| `/logout` | POST | Revoke the current JWT |
| `/me` | GET | Get the authenticated user |
| `/dummy-data` | GET | Return static dummy records |
| `/api/test/protected` | GET | Protected test endpoint |
| `/api/test/echo` | POST | Echo test endpoint |

## Full OAuth Demo

`xuno-auth-demo/` provides the OAuth authorization server, remote MCP server, local HTTPS harness, and Claude custom connector flow.

Use this MCP URL in Claude's custom connector:

```text
https://localhost:3443/mcp
```

See [xuno-auth-demo/README.md](xuno-auth-demo/README.md).
