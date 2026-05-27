from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import uuid4
import webbrowser

from dotenv import load_dotenv
import requests


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

AUTH_SERVER_URL = os.getenv("ENTITY_AUTH_SERVER_URL", "http://localhost:3000")
CALLBACK_PORT = 3002
CLIENT_ID = os.getenv("ENTITY_OAUTH_CLIENT_ID")
CLIENT_SECRET = os.getenv("ENTITY_OAUTH_CLIENT_SECRET")
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/callback"
STATE = str(uuid4())

if not CLIENT_ID:
    raise RuntimeError("Missing required environment variable: ENTITY_OAUTH_CLIENT_ID")

if not CLIENT_SECRET:
    raise RuntimeError("Missing required environment variable: ENTITY_OAUTH_CLIENT_SECRET")


def exchange_code_for_token(code: str) -> dict:
    response = requests.post(
        f"{AUTH_SERVER_URL}/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def fetch_user_info(access_token: str) -> dict:
    response = requests.get(
        f"{AUTH_SERVER_URL}/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def save_access_token(access_token: str) -> None:
    """Replace only the generated token line while preserving the rest of .env."""
    env_path = ROOT / ".env"
    current_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    preserved_lines = [line for line in current_lines if not line.startswith("ENTITY_ACCESS_TOKEN=")]
    preserved_lines.append(f"ENTITY_ACCESS_TOKEN={access_token}")
    env_path.write_text("\n".join(preserved_lines) + "\n", encoding="utf-8")


class CallbackHandler(BaseHTTPRequestHandler):
    """Temporary local callback server that catches the OAuth redirect."""

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path != "/callback":
            self.send_error(404)
            return

        if query.get("state", [""])[0] != STATE:
            self.respond(400, "Invalid OAuth state. Please run python login.py again.")
            self.server.should_stop = True
            return

        code = query.get("code", [""])[0]
        if not code:
            self.respond(400, "Missing authorization code. Please run python login.py again.")
            self.server.should_stop = True
            return

        try:
            token_response = exchange_code_for_token(code)
            user = fetch_user_info(token_response["access_token"])
            save_access_token(token_response["access_token"])

            self.respond(
                200,
                f"""
                <html>
                  <body style="font-family: system-ui, sans-serif; padding: 32px;">
                    <h1>Logged in as {user["email"]}</h1>
                    <p>You can close this browser tab and start the MCP server.</p>
                  </body>
                </html>
                """,
            )
            print(f"✅ Logged in as {user['email']}. Token saved.")
        except requests.RequestException as exc:
            self.respond(500, f"Login failed: {exc}")
        finally:
            self.server.should_stop = True

    def respond(self, status: int, body: str):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format, *_args):
        # Keep the demo output focused on the login result.
        return


def main():
    authorize_url = f"{AUTH_SERVER_URL}/authorize?{urlencode({
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': 'openid profile email',
        'state': STATE,
    })}"

    server = HTTPServer(("127.0.0.1", CALLBACK_PORT), CallbackHandler)
    server.should_stop = False

    print(f"Waiting for entity.co login callback on http://localhost:{CALLBACK_PORT}/callback")
    webbrowser.open(authorize_url)

    while not server.should_stop:
        server.handle_request()

    server.server_close()


if __name__ == "__main__":
    main()
