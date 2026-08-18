#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
printf 'NOTE: compatibility entry point; using the reusable local Node authoring loop.\n'
exec "${SCRIPT_DIR}/materialize-node-analysis.sh" \
  "${1:-${SCRIPT_DIR}/node-k001-regression-authoring.json}"
