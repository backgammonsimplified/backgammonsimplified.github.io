#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
CONFIG="${1:-}"
BOARD_REPO="${BACKGAMMONBOARD_REPO:-}"
CALCULATOR_REPO="${BACKGAMMONCALCULATOR_REPO:-}"
EXPLAINER="${EXPLAINER_REPO:-}"
R_COMMAND="${R_BIN:-R}"

[[ -n "${CONFIG}" ]] || {
  printf 'Usage: BACKGAMMONBOARD_REPO=... BACKGAMMONCALCULATOR_REPO=... EXPLAINER_REPO=... %s CONFIG_JSON\n' "${0##*/}" >&2
  exit 2
}
for value in BOARD_REPO CALCULATOR_REPO EXPLAINER; do
  [[ -n "${!value}" ]] || {
    printf 'ERROR: %s must identify the exact refreshed authority checkout.\n' "${value}" >&2
    exit 1
  }
done

verify_head() {
  local repository="$1"
  local expected="$2"
  local label="$3"
  local observed
  observed="$(git -C "${repository}" rev-parse HEAD)"
  [[ "${observed}" == "${expected}" ]] || {
    printf 'ERROR: %s head differs: expected %s, observed %s\n' "${label}" "${expected}" "${observed}" >&2
    exit 1
  }
}

verify_head "${BOARD_REPO}" "e3a989788758d30a0be065490d29ec48a88a05c0" "backgammonboard"
verify_head "${CALCULATOR_REPO}" "a385a963ed01a6eac083dae7a1b246b1c150b3eb" "backgammoncalculator"
verify_head "${EXPLAINER}" "58522bb078ecda273a11476c60f1875a2255b285" "backgammon-explainer"

if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PYTHON="${REPO_ROOT}/.venv/bin/python"
elif [[ -x "${REPO_ROOT}/.venv/Scripts/python.exe" ]]; then
  PYTHON="${REPO_ROOT}/.venv/Scripts/python.exe"
else
  printf 'ERROR: repository Python environment is unavailable.\n' >&2
  exit 1
fi

"${PYTHON}" - <<'PY'
import numpy
if numpy.__version__ != "2.4.6":
    raise SystemExit("ERROR: frozen HADD generation requires NumPy 2.4.6")
PY

INSTALL_LIBRARY="${REPO_ROOT}/.r-library"
DEPENDENCY_LIBRARIES="${ANALYZER_ENRICHMENT_R_DEPENDENCY_LIBS:-}"
mkdir -p "${INSTALL_LIBRARY}"
export R_LIBS_USER="${INSTALL_LIBRARY}${DEPENDENCY_LIBRARIES:+:${DEPENDENCY_LIBRARIES}}"
"${R_COMMAND}" CMD INSTALL --library="${INSTALL_LIBRARY}" "${BOARD_REPO}"
"${R_COMMAND}" CMD INSTALL --library="${INSTALL_LIBRARY}" "${CALCULATOR_REPO}"

cd "${REPO_ROOT}"
"${PYTHON}" scripts/analysis/analysis_enrichment_materializer.py \
  "${CONFIG}" \
  --explainer-repo "${EXPLAINER}" \
  --verify-repeat
