#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." && pwd)"

bash "${REPO_ROOT}/scripts/setup/preflight.sh" --quick
PYTHON_COMMAND=("${REPO_ROOT}/.venv/Scripts/python.exe")
if [[ ! -x "${PYTHON_COMMAND[0]}" ]]; then
  PYTHON_COMMAND=("${REPO_ROOT}/.venv/bin/python")
fi

cd "${REPO_ROOT}"

printf 'BS quick build gate\n'
printf 'Repository: %s\n\n' "${REPO_ROOT}"

printf '[1/5] Diff and deterministic fixture checks\n'
git diff --check

printf '\n[2/5] JavaScript syntax\n'
node --check site/assets/bs-learn.js
node --check site/assets/bs-learn-scroll.js
node --check site/assets/bs-analysis-results.js
node --check site/assets/bs-analyzer-live.js
node --check site/assets/bs-lesson-analysis.js
node --check scripts/testing/ux/browser/release_ui_browser_check.mjs
node --check scripts/testing/ux/browser/lesson_analysis_browser_check.mjs
node --check scripts/testing/ux/browser/comprehensive_quality_browser_check.mjs
node --check scripts/testing/quality/performance/runtime_performance_baseline.mjs
node --check scripts/testing/quality/browser/isolated_browser_tab.mjs

printf '\n[3/5] Focused JavaScript behavior\n'
node tests/test_learn_filters.js
node tests/test_continuous_learn.js
node tests/test_continuous_research.js
node tests/test_research_filters.js
node tests/test_lesson_analysis.js
node tests/test_release_ui_browser_check.mjs
node tests/test_lesson_analysis_browser_check.mjs
node tests/test_comprehensive_quality_browser_check.mjs
node tests/test_runtime_performance_baseline.mjs
node tests/test_isolated_browser_tab.mjs
node tests/test_analysis_results_viewer.js
node tests/test_analyzer_live.js
node tests/test_analysis_view_materializer.js

printf '\n[4/5] Focused Python contracts\n'
"${PYTHON_COMMAND[@]}" -m unittest \
  tests.test_release_ui_checks \
  tests.test_lesson_analysis \
  tests.test_node_analysis_authoring \
  tests.test_real_checker_analysis \
  tests.test_publication_identity \
  tests.test_environment_setup \
  tests.test_static_inventory \
  tests.test_quality_reports \
  tests.test_analysis_parquet_intake \
  tests.test_accepted_node_canonical_materialization \
  tests.test_analysis_view_materializer \
  tests.test_analyzer_local_preview \
  tests.test_retrieval_workloads \
  tests.test_learn_canonical_consumption \
  -v

printf '\n[5/5] Existing rendered-site representative audit\n'
if [[ -f site/_site/index.html ]]; then
  "${PYTHON_COMMAND[@]}" scripts/testing/build/release_ui_static_check.py \
    --representative-only
else
  printf 'Skipped: site/_site/index.html does not exist.\n'
fi

printf '\nPASS: quick build gate.\n'
