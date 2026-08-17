#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PORT="${1:-8765}"
HOST="127.0.0.1"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/preview-site.sh [PORT]

Bootstraps the rendered site when needed, then serves site/_site while Quarto
watches source files and writes changed pages there. The repository-managed
Python environment is used for Quarto hooks. Social cards are not regenerated.

Examples:
  bash scripts/preview-site.sh
  bash scripts/preview-site.sh 8765

Stop with Ctrl-C.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 1 ]]; then
  printf 'ERROR: Provide zero or one port number.\n\n' >&2
  usage >&2
  exit 2
fi

if [[ ! "${PORT}" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  printf 'ERROR: Port must be an integer from 1 to 65535. Received: %s\n' "${PORT}" >&2
  exit 2
fi

if ! command -v quarto >/dev/null 2>&1; then
  printf 'ERROR: quarto was not found on PATH.\n' >&2
  exit 127
fi

PROJECT_PYTHON="${REPO_ROOT}/.venv/Scripts/python.exe"
if [[ -x "${PROJECT_PYTHON}" ]] &&
  "${PROJECT_PYTHON}" -c 'import sys' >/dev/null 2>&1; then
  PYTHON_COMMAND=("${PROJECT_PYTHON}")
  export PATH="$(dirname "${PROJECT_PYTHON}"):${PATH}"
elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PROJECT_PYTHON="${REPO_ROOT}/.venv/bin/python"
  PYTHON_COMMAND=("${PROJECT_PYTHON}")
  export PATH="$(dirname "${PROJECT_PYTHON}"):${PATH}"
elif command -v py >/dev/null 2>&1; then
  PYTHON_COMMAND=(py)
elif command -v python >/dev/null 2>&1; then
  PYTHON_COMMAND=(python)
else
  printf 'ERROR: Neither project Python, py, nor python was found on PATH.\n' >&2
  exit 127
fi

cd "${REPO_ROOT}"
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export BS_SKIP_SOCIAL_CARDS=1
export BS_PUBLICATION_MODE=development

if [[ ! -f "site/_site/index.html" ]]; then
  printf 'No rendered site found; bootstrapping development render.\n'
  printf 'Python: %s\n\n' "${PYTHON_COMMAND[*]}"
  quarto render site
fi

if [[ ! -f "site/_site/index.html" ]]; then
  printf 'ERROR: bootstrap render did not produce site/_site/index.html.\n' >&2
  exit 1
fi

STATIC_SERVER_PID=""

cleanup() {
  if [[ -n "${STATIC_SERVER_PID}" ]] && kill -0 "${STATIC_SERVER_PID}" 2>/dev/null; then
    kill "${STATIC_SERVER_PID}" 2>/dev/null || true
    wait "${STATIC_SERVER_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT

printf 'BS static preview + render watcher\n'
printf 'Repository: %s\n' "${REPO_ROOT}"
printf 'Python:     %s\n' "${PYTHON_COMMAND[*]}"
printf 'URL:        http://%s:%s/\n' "${HOST}" "${PORT}"
printf 'Serving:    site/_site output\n'
printf 'Watching:   Quarto source changes\n'
printf 'Social:     skipped\n'
printf 'Stop:       Ctrl-C\n\n'

"${PYTHON_COMMAND[@]}" -m http.server "${PORT}" \
  --bind "${HOST}" \
  --directory site/_site &
STATIC_SERVER_PID=$!

sleep 0.25
if ! kill -0 "${STATIC_SERVER_PID}" 2>/dev/null; then
  wait "${STATIC_SERVER_PID}"
  exit 1
fi

quarto preview site \
  --no-serve \
  --no-browser \
  --no-navigate
