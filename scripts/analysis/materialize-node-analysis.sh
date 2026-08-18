#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
CONFIG="${1:-}"
R_COMMAND="${R_BIN:-R}"

[[ -n "${CONFIG}" ]] || {
  printf 'Usage: %s CONFIG_JSON\n' "${0##*/}" >&2
  exit 2
}

if [[ -x "${REPO_ROOT}/.venv/Scripts/python.exe" ]]; then
  PYTHON="${REPO_ROOT}/.venv/Scripts/python.exe"
elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PYTHON="${REPO_ROOT}/.venv/bin/python"
else
  PYTHON="$(command -v python || true)"
fi
[[ -n "${PYTHON}" ]] || { printf 'ERROR: python is unavailable.\n' >&2; exit 1; }

mkdir -p "${REPO_ROOT}/.r-library"
export R_LIBS_USER="${LOCAL_NODE_R_LIBS_USER:-${REPO_ROOT}/.r-library}"

if [[ -n "${BACKGAMMONCALCULATOR_REPO:-}" ]]; then
  "${R_COMMAND}" CMD INSTALL --library="${R_LIBS_USER}" "${BACKGAMMONCALCULATOR_REPO}"
fi
if [[ -n "${BACKGAMMONBOARD_REPO:-}" ]]; then
  "${R_COMMAND}" CMD INSTALL --library="${R_LIBS_USER}" "${BACKGAMMONBOARD_REPO}"
fi

cd "${REPO_ROOT}"
"${PYTHON}" scripts/analysis/materialize_node_analysis.py "${CONFIG}"
