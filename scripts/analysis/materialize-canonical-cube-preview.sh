#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

PACKAGE_ROOT="${CANONICAL_ANALYSIS_PACKAGE:?Set CANONICAL_ANALYSIS_PACKAGE to the verified Canonical package directory}"
PYTHON="${PYTHON_BIN:-${REPO_ROOT}/.venv/bin/python}"
RSCRIPT="${RSCRIPT_BIN:-/usr/bin/Rscript}"
export R_LIBS_USER="${R_LIBS_USER:-${REPO_ROOT}/.r-library}"

EXPECTED_MANIFEST_SHA256="effa2a8bc273be03222d8193c090f96ef3415224af228f0e45678b8e7ec498a7"
CUBE_OCCURRENCE_ID="002fc0917b230a0d4ae13c92c5f46fdfc64b6072bb248f743cd732418e085c0d"

READ_SET="$(mktemp)"
trap 'rm -f "${READ_SET}"' EXIT

"${PYTHON}" \
  "${REPO_ROOT}/scripts/analysis/canonical_parquet_cube_readset.py" \
  "${PACKAGE_ROOT}" \
  --cube-occurrence-id "${CUBE_OCCURRENCE_ID}" \
  --expected-manifest-sha256 "${EXPECTED_MANIFEST_SHA256}" \
  --output "${READ_SET}"

"${RSCRIPT}" --vanilla \
  "${REPO_ROOT}/scripts/render_canonical_cube_preview.R" \
  "${READ_SET}" \
  "${REPO_ROOT}/site/assets/positions/real-analysis/canonical-cube-preview/starting.svg"

"${PYTHON}" \
  "${REPO_ROOT}/scripts/analysis/analysis_view_materializer.py" \
  "${READ_SET}" \
  --output "${REPO_ROOT}/site/data/analyzer-canonical-cube-preview.json" \
  --verify-repeat

printf 'PASS: generated Analyzer Canonical cube preview for %s.\n' "${CUBE_OCCURRENCE_ID}"
