#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
PYTHON="${PYTHON:-${ROOT_DIR}/../.venv/bin/python}"

mkdir -p "${LOG_DIR}"

if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="python3"
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed or not on PATH." >&2
  exit 1
fi

if [[ -f "${ENV_FILE}" ]]; then
  eval "$("${PYTHON}" - "${ENV_FILE}" <<'PY'
from dotenv import dotenv_values
import shlex
import sys

keys = {
    "AUTH_PORT",
    "MCP_HOST",
    "MCP_PORT",
    "MCP_PATH",
    "HTTPS_HARNESS_PORT",
    "ENTITY_AUTH_SERVER_URL",
}
for key, value in dotenv_values(sys.argv[1]).items():
    if key in keys and value is not None:
        print(f"export {key}={shlex.quote(value)}")
PY
)"
fi

export AUTH_PORT="${AUTH_PORT:-3000}"
export MCP_HOST="${MCP_HOST:-127.0.0.1}"
export MCP_PORT="${MCP_PORT:-3001}"
export MCP_PATH="${MCP_PATH:-/mcp}"
export HTTPS_HARNESS_PORT="${HTTPS_HARNESS_PORT:-3443}"
export ENTITY_AUTH_SERVER_URL="${ENTITY_AUTH_SERVER_URL:-http://localhost:${AUTH_PORT}}"

CLOUDFLARED_LOG="${LOG_DIR}/cloudflared.log"
ORIGIN_URL="https://localhost:${HTTPS_HARNESS_PORT}"

cleanup() {
  for pid in ${HARNESS_PID:-} ${MCP_PID:-} ${AUTH_PID:-} ${CLOUDFLARED_PID:-}; do
    if [[ -n "${pid}" ]]; then
      kill "${pid}" >/dev/null 2>&1 || true
    fi
  done
}
trap cleanup EXIT INT TERM

cd "${ROOT_DIR}"

echo "Starting Cloudflare tunnel to ${ORIGIN_URL} ..."
cloudflared tunnel --url "${ORIGIN_URL}" --no-tls-verify >"${CLOUDFLARED_LOG}" 2>&1 &
CLOUDFLARED_PID="$!"

PUBLIC_URL=""
for _ in {1..60}; do
  if ! kill -0 "${CLOUDFLARED_PID}" >/dev/null 2>&1; then
    echo "cloudflared exited before a tunnel URL was available:" >&2
    sed -n '1,120p' "${CLOUDFLARED_LOG}" >&2
    exit 1
  fi

  PUBLIC_URL="$(grep -Eo 'https://[-a-zA-Z0-9]+\.trycloudflare\.com' "${CLOUDFLARED_LOG}" | tail -n 1 || true)"
  if [[ -n "${PUBLIC_URL}" ]]; then
    break
  fi
  sleep 1
done

if [[ -z "${PUBLIC_URL}" ]]; then
  echo "Timed out waiting for a Cloudflare tunnel URL. Recent cloudflared output:" >&2
  sed -n '1,160p' "${CLOUDFLARED_LOG}" >&2
  exit 1
fi

export ENTITY_PUBLIC_AUTH_ISSUER="${PUBLIC_URL}"
export ENTITY_PUBLIC_MCP_URL="${PUBLIC_URL}${MCP_PATH}"

echo "Starting entity.co auth server on http://127.0.0.1:${AUTH_PORT} ..."
"${PYTHON}" auth_server/index.py >"${LOG_DIR}/auth-server.log" 2>&1 &
AUTH_PID="$!"

echo "Starting entity.co MCP server on http://${MCP_HOST}:${MCP_PORT}${MCP_PATH} ..."
"${PYTHON}" mcp_server/index.py >"${LOG_DIR}/mcp-server.log" 2>&1 &
MCP_PID="$!"

echo "Starting local HTTPS harness on ${ORIGIN_URL}${MCP_PATH} ..."
"${ROOT_DIR}/scripts/start-https-harness.sh" >"${LOG_DIR}/https-harness.log" 2>&1 &
HARNESS_PID="$!"

echo
echo "MCP public URL:"
echo "${ENTITY_PUBLIC_MCP_URL}"
echo
echo "OAuth issuer:"
echo "${ENTITY_PUBLIC_AUTH_ISSUER}"
echo
echo "Logs:"
echo "  ${LOG_DIR}/auth-server.log"
echo "  ${LOG_DIR}/mcp-server.log"
echo "  ${LOG_DIR}/https-harness.log"
echo "  ${CLOUDFLARED_LOG}"
echo
echo "Press Ctrl+C to stop all services."

wait
