#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
CHECKER_VIEW="${CHECKER_VIEW:-$HOME/Documents/artifacts/node-k001/analysis-view/checker-analysis-view.json}"
CUBE_VIEW="${CUBE_VIEW:-$HOME/Documents/artifacts/node-k001/lesson-cube-proof/cube-analysis-view.json}"
BACKGAMMONBOARD_REPO="${BACKGAMMONBOARD_REPO:-$HOME/Documents/backgammonboard}"
BACKGAMMONCALCULATOR_REPO="${BACKGAMMONCALCULATOR_REPO:-$HOME/Documents/backgammoncalculator}"
OUTPUT_JSON="${REPO_ROOT}/site/data/analyzer-node-k001-lesson-preview.json"
OUTPUT_ASSETS="${REPO_ROOT}/site/assets/positions/node-k001"
R_COMMAND="${R_BIN:-R}"
RSCRIPT_COMMAND="${RSCRIPT_BIN:-Rscript}"

if [[ -x "${REPO_ROOT}/.venv/Scripts/python.exe" ]]; then
  PYTHON="${REPO_ROOT}/.venv/Scripts/python.exe"
elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PYTHON="${REPO_ROOT}/.venv/bin/python"
else
  PYTHON="$(command -v python || true)"
fi

[[ -n "${PYTHON}" ]] || { printf 'ERROR: python is unavailable.\n' >&2; exit 1; }
[[ -f "${CHECKER_VIEW}" ]] || { printf 'ERROR: checker Node view missing: %s\n' "${CHECKER_VIEW}" >&2; exit 1; }
[[ -f "${CUBE_VIEW}" ]] || { printf 'ERROR: cube Node view missing: %s\n' "${CUBE_VIEW}" >&2; exit 1; }
[[ -d "${BACKGAMMONBOARD_REPO}" ]] || { printf 'ERROR: Backgammonboard checkout missing: %s\n' "${BACKGAMMONBOARD_REPO}" >&2; exit 1; }
[[ -d "${BACKGAMMONCALCULATOR_REPO}" ]] || { printf 'ERROR: Backgammoncalculator checkout missing: %s\n' "${BACKGAMMONCALCULATOR_REPO}" >&2; exit 1; }
command -v "${R_COMMAND}" >/dev/null || { printf 'ERROR: R is unavailable.\n' >&2; exit 1; }
command -v "${RSCRIPT_COMMAND}" >/dev/null || { printf 'ERROR: Rscript is unavailable.\n' >&2; exit 1; }

cd "${REPO_ROOT}"
mkdir -p "${REPO_ROOT}/.r-library"
export R_LIBS_USER="${REPO_ROOT}/.r-library"

"${PYTHON}" scripts/analysis/project_node_k001_lesson_preview.py \
  --checker-view "${CHECKER_VIEW}" \
  --cube-view "${CUBE_VIEW}" \
  --output "${OUTPUT_JSON}"

"${R_COMMAND}" CMD INSTALL --library="${R_LIBS_USER}" "${BACKGAMMONCALCULATOR_REPO}"
"${R_COMMAND}" CMD INSTALL --library="${R_LIBS_USER}" "${BACKGAMMONBOARD_REPO}"

"${RSCRIPT_COMMAND}" --vanilla scripts/analysis/render_node_k001_lesson_assets.R \
  "${CHECKER_VIEW}" \
  "${CUBE_VIEW}" \
  "${OUTPUT_ASSETS}"

printf 'PASS: exact Node K001 checker and cube preview materialized.\n'
printf 'data: %s\n' "${OUTPUT_JSON}"
printf 'assets: %s\n' "${OUTPUT_ASSETS}"
