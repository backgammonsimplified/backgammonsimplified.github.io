#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
PYTHON="${PYTHON_BIN:-${REPO_ROOT}/.venv/bin/python}"

CHECKER_PACKAGE="${CANONICAL_CHECKER_PACKAGE:?Set CANONICAL_CHECKER_PACKAGE to immutable Package A}"
CUBE_PACKAGE="${CANONICAL_CUBE_PACKAGE:?Set CANONICAL_CUBE_PACKAGE to the immutable accepted Learn cube package}"

"${PYTHON}" "${SCRIPT_DIR}/materialize_accepted_node_pair.py" \
  --config "${SCRIPT_DIR}/node-k001-canonical-materialization.json" \
  --checker-package "${CHECKER_PACKAGE}" \
  --cube-package "${CUBE_PACKAGE}"
