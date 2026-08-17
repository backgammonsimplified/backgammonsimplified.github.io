#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

if [[ -x "${REPO_ROOT}/.venv/Scripts/python.exe" ]]; then
  PROJECT_PYTHON="${REPO_ROOT}/.venv/Scripts/python.exe"
elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PROJECT_PYTHON="${REPO_ROOT}/.venv/bin/python"
elif command -v python >/dev/null 2>&1; then
  PROJECT_PYTHON="$(command -v python)"
else
  printf 'ERROR: project Python is unavailable. Run scripts/setup/windows-dev.sh or scripts/setup/setup.sh first.\n' >&2
  exit 127
fi

export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
exec "${PROJECT_PYTHON}" "$@"
