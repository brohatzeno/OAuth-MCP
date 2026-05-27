import contextlib
import os
from typing import Any

import requests
import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route


load_dotenv()

HOST = os.getenv("MCP_HOST", "127.0.0.1")
PORT = int(os.getenv("MCP_PORT", "3001"))
MCP_PATH = os.getenv("MCP_PATH", "/mcp")
AUTH_SERVER_URL = os.getenv("ENTITY_AUTH_SERVER_URL", "http://localhost:3000")
PUBLIC_MCP_URL = os.getenv("ENTITY_PUBLIC_MCP_URL", f"https://localhost:3443{MCP_PATH}").rstrip("/")
PUBLIC_AUTH_ISSUER = os.getenv("ENTITY_PUBLIC_AUTH_ISSUER", "https://localhost:3443").rstrip("/")
ALLOW_UNAUTHENTICATED_LOCAL = os.getenv("ENTITY_ALLOW_UNAUTHENTICATED_LOCAL", "false").lower() == "true"
RESOURCE_METADATA_URL = f"{PUBLIC_AUTH_ISSUER}/.well-known/oauth-protected-resource"
CURRENT_USER: dict[str, str] | None = None
SUPPORTED_SCOPES = ["openid", "profile", "email"]
LOCAL_CLIENT_HOSTS = {"127.0.0.1", "::1", "localhost"}
LOCAL_REQUEST_HOSTS = {"127.0.0.1", "localhost"}

AVAILABLE_TOOLS = [
    "get_company_info",
    "get_employee_list",
    "get_user_profile",
    "get_dummy_data",
]

DUMMY_DATA = {
    "records": [
        {"id": "demo-001", "label": "Sample customer", "status": "active"},
        {"id": "demo-002", "label": "Sample invoice", "status": "pending"},
        {"id": "demo-003", "label": "Sample support ticket", "status": "resolved"},
    ],
    "source": "static-demo",
}


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_mock_employees() -> list[dict[str, str]]:
    # Directory identities are also sourced from .env so login identifiers are not hardcoded.
    employees: list[dict[str, str]] = []

    for index in range(1, 51):
        prefix = f"ENTITY_EMPLOYEE_{index}"
        email = os.getenv(f"{prefix}_EMAIL", "").strip().lower()

        if not email:
            continue

        employees.append(
            {
                "name": os.getenv(f"{prefix}_NAME", email.split("@")[0]).strip(),
                "email": email,
                "role": os.getenv(f"{prefix}_ROLE", "Employee").strip(),
            }
        )

    if not employees:
        raise RuntimeError("At least one ENTITY_EMPLOYEE_* login must be configured.")

    return employees


MOCK_EMPLOYEES = load_mock_employees()
LOCAL_DEMO_USER = {
    "name": MOCK_EMPLOYEES[0]["name"],
    "email": MOCK_EMPLOYEES[0]["email"],
}


def verify_token(access_token: str | None) -> dict[str, Any]:
    """Validate a bearer token from the current MCP request."""
    if not access_token:
        return {"valid": False, "error": "Missing bearer token."}
    try:
        response = requests.get(
            f"{AUTH_SERVER_URL}/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5,
        )
    except requests.RequestException as exc:
        return {"valid": False, "error": f"Could not reach auth backend: {exc}"}

    if not response.ok:
        return {"valid": False, "error": f"Auth backend rejected token with HTTP {response.status_code}."}

    return {"valid": True, "user": response.json()}


# Stateless JSON responses keep the demo easy to test with curl and Claude MCP clients.
mcp = FastMCP(
    "entity-enterprise-mcp",
    stateless_http=True,
    json_response=True,
    streamable_http_path=MCP_PATH,
)


@mcp.tool()
def get_company_info() -> dict[str, Any]:
    """Return entity.co company details."""
    return {
        "name": "entity.co",
        "domain": "entity.co",
        "employeeCount": 128,
        "hqLocation": "Demo City, USA",
        "developedBy": "entity.co",
        "serviceAreas": [
            "internal tooling",
            "customer operations",
            "workflow automation",
        ],
        "marketFocus": "Demonstrating authenticated MCP tools with safe static data.",
        "usOperations": "Demo operations for local connector testing.",
    }


@mcp.tool()
def get_employee_list() -> dict[str, Any]:
    """Return the demo employee directory with names, emails, and roles."""
    return {"employees": MOCK_EMPLOYEES}


@mcp.tool()
def get_user_profile() -> dict[str, str]:
    """Return the currently logged-in employee from the validated access token."""
    return CURRENT_USER or {}


@mcp.tool()
def get_dummy_data() -> dict[str, Any]:
    """Return static dummy data for connection testing."""
    return DUMMY_DATA


async def health(request: Request) -> JSONResponse:
    auth_state = verify_request(request)
    return JSONResponse(
        {
            "status": "ok" if auth_state["valid"] else "auth_required",
            "company": "entity.co",
            "user": auth_state.get("user"),
            "availableTools": AVAILABLE_TOOLS if auth_state["valid"] else [],
            "error": None if auth_state["valid"] else auth_state["error"],
        }
    )


async def protected_resource_metadata(_request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "resource": PUBLIC_MCP_URL,
            "authorization_servers": [PUBLIC_AUTH_ISSUER],
            "scopes_supported": SUPPORTED_SCOPES,
            "bearer_methods_supported": ["header"],
        }
    )


def verify_request(request: Request) -> dict[str, Any]:
    if ALLOW_UNAUTHENTICATED_LOCAL and is_loopback_request(request):
        return {"valid": True, "user": LOCAL_DEMO_USER, "auth_mode": "local_bypass"}

    auth_header = request.headers.get("authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme != "Bearer":
        token = None
    return verify_token(token)


def is_loopback_request(request: Request) -> bool:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    client_host = request.client.host if request.client else ""
    forwarded_host = request.headers.get("x-forwarded-host", request.headers.get("host", ""))
    request_host = forwarded_host.split(":", 1)[0].lower()
    is_local_client = forwarded_for in LOCAL_CLIENT_HOSTS or client_host in LOCAL_CLIENT_HOSTS
    return is_local_client and request_host in LOCAL_REQUEST_HOSTS


class AuthGate:
    """Small ASGI wrapper that starts the OAuth flow when MCP traffic is unauthenticated."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        global CURRENT_USER

        request = Request(scope, receive)
        auth_state = verify_request(request)

        if not auth_state["valid"]:
            response = JSONResponse(
                {
                    "error": "entity_auth_required",
                    "message": auth_state["error"],
                },
                status_code=401,
                headers={
                    "WWW-Authenticate": f'Bearer resource_metadata="{RESOURCE_METADATA_URL}"',
                },
            )
            await response(scope, receive, send)
            return

        CURRENT_USER = auth_state["user"]
        await self.app(scope, receive, send)


@contextlib.asynccontextmanager
async def lifespan(_app: Starlette):
    # The MCP session manager must be running while the ASGI server accepts MCP requests.
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource", protected_resource_metadata, methods=["GET"]),
        Route(
            "/.well-known/oauth-protected-resource/{resource_path:path}",
            protected_resource_metadata,
            methods=["GET"],
        ),
        Mount("", app=AuthGate(mcp.streamable_http_app())),
    ],
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    print(f"entity.co MCP server running on http://{HOST}:{PORT}{MCP_PATH}")
    print(f"Public MCP URL advertised as {PUBLIC_MCP_URL}")
    print("MCP requests now trigger OAuth when no valid bearer token is present.")
    if ALLOW_UNAUTHENTICATED_LOCAL:
        print("Local unauthenticated MCP mode is enabled for loopback requests only.")

    uvicorn.run(app, host=HOST, port=PORT)
