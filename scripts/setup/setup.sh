#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

require_file() {
  [[ -f "$1" ]] || { printf 'Missing repository dependency source: %s\n' "$1" >&2; exit 1; }
}

require_file "${REPO_ROOT}/social_generator/requirements-social.txt"
require_file "${REPO_ROOT}/social_generator/requirements-social.R"
require_file "${REPO_ROOT}/scripts/analysis/requirements.txt"
require_file "${REPO_ROOT}/scripts/analysis/requirements.R"
require_file "${REPO_ROOT}/scripts/setup/install-r-dependencies.R"
require_file "${REPO_ROOT}/scripts/setup/preflight.py"
require_file "${REPO_ROOT}/site/_quarto.yml"

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File \
      "${SCRIPT_DIR}/windows/configure-project.ps1" -RepoRoot "${REPO_ROOT}"
    VENV_PYTHON="${REPO_ROOT}/.venv/Scripts/python.exe"
    ;;
  Linux)
    bash "${SCRIPT_DIR}/linux/configure-project.sh" "${REPO_ROOT}"
    VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"
    ;;
  *)
    printf 'Unsupported platform: %s\n' "$(uname -s)" >&2
    exit 2
    ;;
esac

printf 'Installing Analyzer materializer Python dependencies...\n'
"${VENV_PYTHON}" -m pip install -r "${REPO_ROOT}/scripts/analysis/requirements.txt"
"${VENV_PYTHON}" -m pip check
"${VENV_PYTHON}" -c 'import duckdb; print("DuckDB", duckdb.__version__)'

printf 'Installing Analyzer board-renderer R dependencies...\n'
mkdir -p "${REPO_ROOT}/.r-library"
export R_LIBS_USER="${REPO_ROOT}/.r-library"
RSCRIPT_COMMAND="${RSCRIPT_BIN:-Rscript}"
command -v "${RSCRIPT_COMMAND}" >/dev/null || {
  printf 'Required system tool is missing: %s\n' "${RSCRIPT_COMMAND}" >&2
  exit 1
}
"${RSCRIPT_COMMAND}" --vanilla \
  "${REPO_ROOT}/scripts/setup/install-r-dependencies.R" \
  "${REPO_ROOT}/.r-library" \
  "${REPO_ROOT}/scripts/analysis/requirements.R"
