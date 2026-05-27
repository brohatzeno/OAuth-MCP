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
    "ENTITY_PUBLIC_AUTH_ISSUER",
    "ENTITY_PUBLIC_MCP_URL",
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
export ENTITY_PUBLIC_AUTH_ISSUER="${ENTITY_PUBLIC_AUTH_ISSUER:-https://localhost:${HTTPS_HARNESS_PORT}}"
export ENTITY_PUBLIC_MCP_URL="${ENTITY_PUBLIC_MCP_URL:-${ENTITY_PUBLIC_AUTH_ISSUER}${MCP_PATH}}"

cleanup() {
  for pid in ${HARNESS_PID:-} ${MCP_PID:-} ${AUTH_PID:-}; do
    if [[ -n "${pid}" ]]; then
      kill "${pid}" >/dev/null 2>&1 || true
    fi
  done
}
trap cleanup EXIT INT TERM

cd "${ROOT_DIR}"

echo "Starting entity.co auth server on http://127.0.0.1:${AUTH_PORT} ..."
"${PYTHON}" auth_server/index.py >"${LOG_DIR}/auth-server.log" 2>&1 &
AUTH_PID="$!"

echo "Starting entity.co MCP server on http://${MCP_HOST}:${MCP_PORT}${MCP_PATH} ..."
"${PYTHON}" mcp_server/index.py >"${LOG_DIR}/mcp-server.log" 2>&1 &
MCP_PID="$!"

echo "Starting local HTTPS harness on ${ENTITY_PUBLIC_AUTH_ISSUER}${MCP_PATH} ..."
"${ROOT_DIR}/scripts/start-https-harness.sh" >"${LOG_DIR}/https-harness.log" 2>&1 &
HARNESS_PID="$!"

echo
echo "MCP stack is running."
echo "Local connector URL: ${ENTITY_PUBLIC_MCP_URL}"
echo "OAuth issuer: ${ENTITY_PUBLIC_AUTH_ISSUER}"
echo
echo "Logs:"
echo "  ${LOG_DIR}/auth-server.log"
echo "  ${LOG_DIR}/mcp-server.log"
echo "  ${LOG_DIR}/https-harness.log"
echo
echo "Press Ctrl+C to stop all services."

wait
