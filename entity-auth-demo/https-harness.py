from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
import ssl


HOST = "127.0.0.1"
HTTPS_PORT = int(os.getenv("HTTPS_HARNESS_PORT", "3443"))
BACKEND_HOST = "127.0.0.1"
MCP_PORT = int(os.getenv("MCP_PORT", "3001"))
AUTH_PORT = int(os.getenv("AUTH_PORT", "3000"))
CERT_DIR = Path(__file__).resolve().parent / "certs"
CERT_FILE = CERT_DIR / "localhost.pem"
KEY_FILE = CERT_DIR / "localhost-key.pem"

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
CORS_RESPONSE_HEADERS = {
    "access-control-allow-origin",
    "access-control-allow-credentials",
    "access-control-allow-methods",
    "access-control-allow-headers",
    "access-control-expose-headers",
    "access-control-max-age",
}
AUTH_ROUTE_PREFIXES = (
    "/authorize",
    "/token",
    "/userinfo",
    "/register",
    "/.well-known/oauth-authorization-server",
    "/.well-known/openid-configuration",
)


class LocalHttpsProxy(BaseHTTPRequestHandler):
    """Tiny local HTTPS reverse proxy for the MCP server."""

    def do_GET(self):
        self.forward()

    def do_POST(self):
        self.forward()

    def do_DELETE(self):
        self.forward()

    def do_HEAD(self):
        self.forward()

    def do_OPTIONS(self):
        self.send_response(204)
        self.add_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,HEAD,OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            self.headers.get("Access-Control-Request-Headers", "authorization,content-type,mcp-session-id"),
        )
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def add_cors_headers(self):
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Access-Control-Expose-Headers", "WWW-Authenticate,Mcp-Session-Id")

    def forward(self):
        content_length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(content_length) if content_length else None

        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "host"
        }
        headers["X-Forwarded-For"] = self.client_address[0]
        headers["X-Forwarded-Proto"] = "https"
        headers["X-Forwarded-Host"] = self.headers.get("Host", f"localhost:{HTTPS_PORT}")

        backend_port = AUTH_PORT if self.path.startswith(AUTH_ROUTE_PREFIXES) else MCP_PORT
        connection = HTTPConnection(BACKEND_HOST, backend_port, timeout=30)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            response_body = response.read()

            self.send_response(response.status, response.reason)
            for key, value in response.getheaders():
                lower_key = key.lower()
                if lower_key not in HOP_BY_HOP_HEADERS and lower_key not in CORS_RESPONSE_HEADERS:
                    self.send_header(key, value)
            self.add_cors_headers()
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(response_body)
        finally:
            connection.close()

    def log_message(self, format, *args):
        print(f"[https-harness] {self.address_string()} - {format % args}")


def main():
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        raise RuntimeError(
            "Missing local TLS certificate. Run ./scripts/start-https-harness.sh to generate one."
        )

    server = ThreadingHTTPServer((HOST, HTTPS_PORT), LocalHttpsProxy)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    server.socket = context.wrap_socket(server.socket, server_side=True)

    print(f"Local HTTPS MCP harness running at https://localhost:{HTTPS_PORT}/mcp")
    print(f"Proxying /mcp to http://localhost:{MCP_PORT}")
    print(f"Proxying OAuth endpoints to http://localhost:{AUTH_PORT}")
    print("Keep this terminal open while testing.")
    server.serve_forever()


if __name__ == "__main__":
    main()
