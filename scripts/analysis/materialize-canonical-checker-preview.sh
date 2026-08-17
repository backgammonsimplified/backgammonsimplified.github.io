#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

PACKAGE_ROOT="${CANONICAL_ANALYSIS_PACKAGE:?Set CANONICAL_ANALYSIS_PACKAGE to the verified Canonical package directory}"
PYTHON="${PYTHON_BIN:-${REPO_ROOT}/.venv/bin/python}"

EXPECTED_MANIFEST_SHA256="effa2a8bc273be03222d8193c090f96ef3415224af228f0e45678b8e7ec498a7"
DECISION_ID="b909630c811a0214b8156e068b88ebeb9a064a56bfec3ae5af8c6afe45278d07"
GNU_POSITION_ID="3N0DAAD0HDMABw"

READ_SET="$(mktemp)"
trap 'rm -f "${READ_SET}"' EXIT

"${PYTHON}" "${REPO_ROOT}/scripts/analysis/canonical_parquet_readset.py" \
  "${PACKAGE_ROOT}" \
  --decision-id "${DECISION_ID}" \
  --actual-ply 4 \
  --expected-manifest-sha256 "${EXPECTED_MANIFEST_SHA256}" \
  --presentation-sidecar "${REPO_ROOT}/site/data/analyzer-retained-checker-preview.json" \
  --presentation-analysis-id retained-checker-preview \
  --expected-gnu-position-id "${GNU_POSITION_ID}" \
  --output "${READ_SET}"

"${PYTHON}" "${REPO_ROOT}/scripts/analysis/analysis_view_materializer.py" \
  "${READ_SET}" \
  --output "${REPO_ROOT}/site/data/analyzer-canonical-checker-preview.json" \
  --verify-repeat

printf 'PASS: generated Analyzer Canonical checker preview.\n'
