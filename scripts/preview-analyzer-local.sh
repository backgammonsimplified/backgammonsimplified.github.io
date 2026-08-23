#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PORT="${1:-8765}"
ANALYZER_PYTHON="${BS_ANALYZER_PYTHON:-${REPO_ROOT}/.venv/bin/python}"
SERVER_CONFIG="${BS_ANALYZER_SERVER_CONFIG:-}"

if [[ ! -x "${ANALYZER_PYTHON}" ]]; then
  printf 'ERROR: Set BS_ANALYZER_PYTHON to Python with backgammon-node 0.1.0 installed.\n' >&2
  exit 127
fi
if [[ ! "${PORT}" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  printf 'ERROR: Port must be an integer from 1 to 65535.\n' >&2
  exit 2
fi

cd "${REPO_ROOT}"
export BS_SKIP_SOCIAL_CARDS=1
export BS_PUBLICATION_MODE=development
quarto render site/analyze/index.qmd

# WSL only forwards explicitly named environment variables to a native Windows
# Python process. Native Linux/macOS/Windows runs do not need this addition.
if [[ "${ANALYZER_PYTHON}" == *.exe ]]; then
  NODE_RUNTIME_VARIABLE="B""MS_WINDOWS_GNU_RUNTIME_ROOT"
  export WSLENV="${NODE_RUNTIME_VARIABLE}${WSLENV:+:${WSLENV}}"
fi

server_args=()
if [[ -n "${SERVER_CONFIG}" ]]; then
  [[ -f "${SERVER_CONFIG}" ]] || {
    printf 'ERROR: BS_ANALYZER_SERVER_CONFIG is not a readable file.\n' >&2
    exit 2
  }
  server_args+=(--server-config "${SERVER_CONFIG}")
fi

exec "${ANALYZER_PYTHON}" scripts/analyzer_local_preview.py \
  --port "${PORT}" \
  "${server_args[@]}"
