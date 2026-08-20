#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
BACKGAMMONBOARD_REPO="${BACKGAMMONBOARD_REPO:-$HOME/Documents/backgammonboard}"
BACKGAMMONCALCULATOR_REPO="${BACKGAMMONCALCULATOR_REPO:-$HOME/Documents/backgammoncalculator}"
RSCRIPT_COMMAND="${RSCRIPT_BIN:-Rscript}"
R_COMMAND="${R_BIN:-R}"

if [[ -x "${REPO_ROOT}/.venv/Scripts/python.exe" ]]; then
  PYTHON="${REPO_ROOT}/.venv/Scripts/python.exe"
elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PYTHON="${REPO_ROOT}/.venv/bin/python"
else
  printf 'ERROR: repository .venv is missing; run the supported setup command first.\n' >&2
  exit 1
fi

[[ -d "${BACKGAMMONBOARD_REPO}" ]] || {
  printf 'ERROR: Backgammonboard checkout not found: %s\n' "${BACKGAMMONBOARD_REPO}" >&2
  printf 'Set BACKGAMMONBOARD_REPO to the current backgammonboard checkout.\n' >&2
  exit 1
}
[[ -d "${BACKGAMMONCALCULATOR_REPO}" ]] || {
  printf 'ERROR: Backgammoncalculator checkout not found: %s\n' "${BACKGAMMONCALCULATOR_REPO}" >&2
  printf 'Set BACKGAMMONCALCULATOR_REPO to the current backgammoncalculator checkout.\n' >&2
  exit 1
}
command -v "${RSCRIPT_COMMAND}" >/dev/null || {
  printf 'ERROR: Rscript is unavailable: %s\n' "${RSCRIPT_COMMAND}" >&2
  exit 1
}
command -v "${R_COMMAND}" >/dev/null || {
  printf 'ERROR: R is unavailable: %s\n' "${R_COMMAND}" >&2
  exit 1
}

cd "${REPO_ROOT}"
mkdir -p "${REPO_ROOT}/.r-library"
export R_LIBS_USER="${REPO_ROOT}/.r-library"
export BACKGAMMONCALCULATOR_REPO

"${PYTHON}" scripts/analysis/project_retained_checker_preview.py

printf 'Installing current local Backgammoncalculator checkout into repository R library...\n'
"${R_COMMAND}" CMD INSTALL \
  --library="${R_LIBS_USER}" \
  "${BACKGAMMONCALCULATOR_REPO}"

printf 'Installing current local Backgammonboard checkout into repository R library...\n'
"${R_COMMAND}" CMD INSTALL \
  --library="${R_LIBS_USER}" \
  "${BACKGAMMONBOARD_REPO}"

"${RSCRIPT_COMMAND}" --vanilla scripts/render_real_checker_assets.R \
  fixtures/real-analysis/checker-sage-gnu-disagreement-001 \
  site/data/checker-sage-gnu-disagreement-001.json \
  "${BACKGAMMONBOARD_REPO}" \
  site/assets/positions/real-analysis/checker-sage-gnu-disagreement-001

printf 'PASS: retained Analyzer checker preview JSON and Backgammonboard SVGs regenerated.\n'
