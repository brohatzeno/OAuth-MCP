from datetime import datetime, timedelta, timezone
import base64
import hashlib
from html import escape
import json
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode
from uuid import uuid4

import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse


load_dotenv()

PORT = int(os.getenv("AUTH_PORT", "3000"))
JWT_SECRET = os.getenv("ENTITY_JWT_SECRET")
OAUTH_CLIENT_ID = os.getenv("ENTITY_OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("ENTITY_OAUTH_CLIENT_SECRET")
PUBLIC_ISSUER = os.getenv("ENTITY_PUBLIC_AUTH_ISSUER", "http://localhost:3000").rstrip("/")
ROOT_DIR = Path(__file__).resolve().parents[1]
OAUTH_CLIENTS_FILE = ROOT_DIR / ".oauth-clients.json"
SUPPORTED_SCOPES = ["openid", "profile", "email"]
ACCESS_TOKEN_TTL_SECONDS = 3600
AUTH_CODE_TTL_MINUTES = 5
JWT_AUDIENCE = "entity-mcp-demo"


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_employees() -> dict[str, dict[str, str]]:
    # This demo keeps employees in memory, but all credential values come from .env.
    # A real identity provider would validate against a database or directory.
    employees = {}

    for index in range(1, 51):
        prefix = f"ENTITY_EMPLOYEE_{index}"
        email = os.getenv(f"{prefix}_EMAIL", "").strip().lower()
        password = os.getenv(f"{prefix}_PASSWORD", "")

        if not email and not password:
            continue
        if not email or not password:
            raise RuntimeError(
                f"{prefix}_EMAIL and {prefix}_PASSWORD must both be set."
            )

        employees[email] = {
            "email": email,
            "password": password,
            "name": os.getenv(f"{prefix}_NAME", email.split("@")[0]).strip(),
            "role": os.getenv(f"{prefix}_ROLE", "Employee").strip(),
        }

    if not employees:
        raise RuntimeError("At least one ENTITY_EMPLOYEE_* login must be configured.")

    return employees


if not JWT_SECRET:
    raise RuntimeError("Missing required environment variable: ENTITY_JWT_SECRET")

if not OAUTH_CLIENT_ID:
    raise RuntimeError("Missing required environment variable: ENTITY_OAUTH_CLIENT_ID")

if not OAUTH_CLIENT_SECRET:
    raise RuntimeError("Missing required environment variable: ENTITY_OAUTH_CLIENT_SECRET")


EMPLOYEES = load_employees()
DEMO_USER_HINT = ", ".join(EMPLOYEES.keys())

# Authorization codes are temporary one-time tickets created after login.
AUTHORIZATION_CODES: dict[str, dict] = {}


def base_oauth_clients() -> dict[str, dict]:
    return {
        OAUTH_CLIENT_ID: {
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "redirect_uris": [],
            "token_endpoint_auth_method": "client_secret_post",
        }
    }


def load_oauth_clients() -> dict[str, dict]:
    clients = base_oauth_clients()
    if OAUTH_CLIENTS_FILE.exists():
        clients.update(json.loads(OAUTH_CLIENTS_FILE.read_text(encoding="utf-8")))
    return clients


def save_oauth_clients() -> None:
    dynamic_clients = {
        client_id: client
        for client_id, client in OAUTH_CLIENTS.items()
        if client_id != OAUTH_CLIENT_ID
    }
    OAUTH_CLIENTS_FILE.write_text(json.dumps(dynamic_clients, indent=2) + "\n", encoding="utf-8")


OAUTH_CLIENTS = load_oauth_clients()

app = FastAPI(title="entity.co Mock OAuth Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def render_login_page(
    client_id: str,
    redirect_uri: str,
    state: str = "",
    scope: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "",
    error: str = "",
) -> str:
    """Return a stakeholder-friendly branded login page."""

    error_html = f'<div class="error">{escape(error)}</div>' if error else ""

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>entity.co - Company Login</title>
    <style>
      :root {{ --brand: #00a86b; --ink: #202033; --muted: #666a80; --line: #e7e7f2; }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: var(--ink);
        background: #f7f7fc;
      }}
      main {{
        width: min(420px, calc(100vw - 32px));
        padding: 32px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: white;
        box-shadow: 0 18px 60px rgba(28, 28, 70, 0.12);
      }}
      .mark {{
        width: 44px;
        height: 44px;
        display: grid;
        place-items: center;
        border-radius: 8px;
        color: white;
        background: var(--brand);
        font-weight: 800;
        margin-bottom: 18px;
      }}
      h1 {{ margin: 0 0 8px; font-size: 24px; letter-spacing: 0; }}
      p {{ margin: 0 0 24px; color: var(--muted); line-height: 1.45; }}
      label {{ display: block; margin: 16px 0 6px; font-size: 14px; font-weight: 650; }}
      input {{
        width: 100%;
        min-height: 44px;
        border: 1px solid #d8d8e8;
        border-radius: 6px;
        padding: 10px 12px;
        font-size: 15px;
      }}
      input:focus {{ outline: 3px solid rgba(0, 168, 107, 0.2); border-color: var(--brand); }}
      button {{
        width: 100%;
        min-height: 46px;
        margin-top: 24px;
        border: 0;
        border-radius: 6px;
        color: white;
        background: var(--brand);
        font-size: 15px;
        font-weight: 750;
        cursor: pointer;
      }}
      .error {{
        padding: 10px 12px;
        border-radius: 6px;
        color: #8a1f28;
        background: #fff0f1;
        margin-bottom: 18px;
        font-size: 14px;
      }}
      .hint {{ margin-top: 18px; font-size: 13px; color: var(--muted); }}
    </style>
  </head>
  <body>
    <main>
      <div class="mark">E</div>
      <h1>entity.co - Company Login</h1>
      <p>Sign in with your entity.co credentials to continue to Claude Desktop.</p>
      {error_html}
      <form method="post" action="/authorize">
        <input type="hidden" name="client_id" value="{escape(client_id)}" />
        <input type="hidden" name="redirect_uri" value="{escape(redirect_uri)}" />
        <input type="hidden" name="state" value="{escape(state)}" />
        <input type="hidden" name="scope" value="{escape(scope)}" />
        <input type="hidden" name="code_challenge" value="{escape(code_challenge)}" />
        <input type="hidden" name="code_challenge_method" value="{escape(code_challenge_method)}" />
        <label for="email">Email</label>
        <input id="email" name="email" type="email" autocomplete="username" placeholder="name@gmail.com" required />
        <label for="password">Password</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required />
        <button type="submit">Sign in</button>
      </form>
      <div class="hint">Demo users: {escape(DEMO_USER_HINT)}</div>
    </main>
  </body>
</html>"""


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "company": "entity.co"}


def decode_basic_client_auth(auth_header: str) -> tuple[str | None, str | None]:
    scheme, _, encoded = auth_header.partition(" ")
    if scheme != "Basic" or not encoded:
        return None, None

    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except Exception:
        return None, None

    client_id, separator, client_secret = decoded.partition(":")
    if not separator:
        return None, None

    return client_id, client_secret


def authorization_server_metadata() -> dict:
    return {
        "issuer": PUBLIC_ISSUER,
        "authorization_endpoint": f"{PUBLIC_ISSUER}/authorize",
        "token_endpoint": f"{PUBLIC_ISSUER}/token",
        "registration_endpoint": f"{PUBLIC_ISSUER}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic", "none"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": SUPPORTED_SCOPES,
    }


@app.get("/.well-known/oauth-authorization-server")
def oauth_authorization_server_metadata() -> dict:
    return authorization_server_metadata()


@app.get("/.well-known/openid-configuration")
def openid_configuration() -> dict:
    return {
        **authorization_server_metadata(),
        "userinfo_endpoint": f"{PUBLIC_ISSUER}/userinfo",
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["HS256"],
    }


@app.post("/register")
async def register_client(request: Request) -> JSONResponse:
    metadata = await request.json()
    client_id = f"entity-dcr-{uuid4()}"
    token_auth_method = metadata.get("token_endpoint_auth_method", "none")

    client = {
        **metadata,
        "client_id": client_id,
        "client_id_issued_at": int(datetime.now(timezone.utc).timestamp()),
        "token_endpoint_auth_method": token_auth_method,
    }

    if token_auth_method != "none":
        client["client_secret"] = str(uuid4())
        client["client_secret_expires_at"] = 0

    OAUTH_CLIENTS[client_id] = client
    save_oauth_clients()
    return JSONResponse(client, status_code=201)


@app.get("/authorize", response_class=HTMLResponse)
def authorize_form(
    response_type: Optional[str] = None,
    client_id: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    state: str = "",
    scope: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "",
) -> HTMLResponse:
    if response_type and response_type != "code":
        raise HTTPException(status_code=400, detail="Only response_type=code is supported in this demo.")

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=400, detail="Missing required OAuth parameters: client_id and redirect_uri.")

    if client_id not in OAUTH_CLIENTS:
        raise HTTPException(status_code=401, detail="Invalid OAuth client_id.")

    if code_challenge_method and code_challenge_method != "S256":
        raise HTTPException(status_code=400, detail="Only S256 PKCE is supported.")

    return HTMLResponse(render_login_page(client_id, redirect_uri, state, scope, code_challenge, code_challenge_method))


@app.post("/authorize", response_class=HTMLResponse)
def authorize_submit(
    email: str = Form(...),
    password: str = Form(...),
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    state: str = Form(""),
    scope: str = Form(""),
    code_challenge: str = Form(""),
    code_challenge_method: str = Form(""),
):
    if client_id not in OAUTH_CLIENTS:
        raise HTTPException(status_code=401, detail="Invalid OAuth client_id.")

    employee = EMPLOYEES.get(email.strip().lower())

    if not employee or employee["password"] != password:
        return HTMLResponse(
            render_login_page(
                client_id,
                redirect_uri,
                state,
                scope,
                code_challenge,
                code_challenge_method,
                "Invalid email or password.",
            ),
            status_code=401,
        )

    # Create a short-lived code and associate it with the employee who signed in.
    code = str(uuid4())
    AUTHORIZATION_CODES[code] = {
        "email": employee["email"],
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=AUTH_CODE_TTL_MINUTES),
    }

    redirect_params = {"code": code}
    if state:
        redirect_params["state"] = state

    separator = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(url=f"{redirect_uri}{separator}{urlencode(redirect_params)}", status_code=302)


def verify_pkce(code_verifier: str, code_challenge: str) -> bool:
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    computed = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return computed == code_challenge


def valid_client_credentials(client_id: str | None, client_secret: str | None) -> bool:
    if not client_id or client_id not in OAUTH_CLIENTS:
        return False

    client = OAUTH_CLIENTS[client_id]
    auth_method = client.get("token_endpoint_auth_method", "none")

    if auth_method == "none":
        return True

    return client_secret == client.get("client_secret")


@app.post("/token")
async def token(request: Request) -> JSONResponse:
    form = await request.form()
    grant_type = form.get("grant_type")
    code = form.get("code")
    basic_client_id, basic_client_secret = decode_basic_client_auth(request.headers.get("authorization", ""))
    client_id = basic_client_id or form.get("client_id")
    client_secret = basic_client_secret or form.get("client_secret")
    redirect_uri = form.get("redirect_uri")
    code_verifier = form.get("code_verifier", "")

    if grant_type and grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    if not valid_client_credentials(client_id, client_secret):
        return JSONResponse({"error": "invalid_client"}, status_code=401)

    record = AUTHORIZATION_CODES.get(str(code))
    if not record or record["expires_at"] < datetime.now(timezone.utc):
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Code is invalid or expired."},
            status_code=400,
        )

    if redirect_uri != record["redirect_uri"]:
        return JSONResponse({"error": "invalid_grant", "error_description": "Redirect URI mismatch."}, status_code=400)

    if record["code_challenge"] and not verify_pkce(str(code_verifier), record["code_challenge"]):
        return JSONResponse({"error": "invalid_grant", "error_description": "PKCE verification failed."}, status_code=400)

    del AUTHORIZATION_CODES[str(code)]
    employee = EMPLOYEES[record["email"]]

    # The JWT is the access token Claude's MCP server will later verify via /userinfo.
    access_token = jwt.encode(
        {
            "email": employee["email"],
            "name": employee["name"],
            "exp": datetime.now(timezone.utc) + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS),
            "iss": PUBLIC_ISSUER,
            "aud": JWT_AUDIENCE,
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    return JSONResponse(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        }
    )


@app.get("/userinfo")
def userinfo(request: Request) -> JSONResponse:
    auth_header = request.headers.get("authorization", "")
    scheme, _, token = auth_header.partition(" ")

    if scheme != "Bearer" or not token:
        return JSONResponse({"error": "missing_token"}, status_code=401)

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            issuer=PUBLIC_ISSUER,
            audience=JWT_AUDIENCE,
        )
    except jwt.PyJWTError:
        return JSONResponse({"error": "invalid_token"}, status_code=401)

    return JSONResponse({"name": payload["name"], "email": payload["email"]})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=PORT)
