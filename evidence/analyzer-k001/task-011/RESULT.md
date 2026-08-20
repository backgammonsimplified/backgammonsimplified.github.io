# Analyzer K001 Task 011 interactive Node loop result

Status: PASS

Task: implement-interactive-position-id-node-analysis-loop-v1

Starting implementation head: 3658e09f1cc3e09121761d18391fc4deb03bda7c

Final implementation head: 382fd9d3c58102275910e839c386c41c91713ab4

## Product-path gates

| Gate | Result |
|---|---|
| Complete GNUID input and pre-submit validation | PASS |
| Non-golden checker through live Node and shared viewer | PASS |
| Non-golden cube through live Node and shared viewer | PASS |
| Identical-request Node cache/reuse | PASS |
| Browser presentation-only boundary | PASS |
| Golden engine rerun | NO |
| D1, Corpus, or Canonical writes | NONE |
| Sage/GNU benchmark isolation | PASS |

Required product-path blockers: 0

## Refreshed authority

- Control Tower: backgammonsimplified/control-tower master at 168a10e754c1120b146b0d5a262e7f928e90b65b
- Task Management: backgammonsimplified/task-management milestone/analyzer-k001 at 42d06c4525a8c8de7e5ef6b1526ddee2a19276ef
- Durable prompt: milestones/analyzer-k001/prompts/011-interactive-position-id-node-analysis-loop.md
- Accepted website base / golden PR #15: 3658e09f1cc3e09121761d18391fc4deb03bda7c
- Node PR #1, left-brain: fb6a121474517c29b66d959d579a9282a61280b2
- Node package / parser package: backgammon-node 0.1.0 / backgammon-engine-kit 0.3.0
- GNU profile: gnu-1.08.003-mingw-20240428-1ply-cubeful-noiseless-windows
- Producer identity SHA-256: b785713f755b9059dd7187ff07aec7a47372ccb393f7bd026a60acf7550f1cbf

## Actual non-golden product proof

The rendered /analyze/ product route accepted complete GNUIDs and drove the loopback-only development adapter. The adapter invoked the accepted Node submit, one-shot worker, and analysis-view commands. Node retained request normalization, analysis identity, queue, worker, engine execution, parsing, status, result, and deterministic view semantics.

The checker request used 4HPwATDgc/ABMA:cAnqAAAAAAAE with dice 4 and 2. It produced analysis key sha256-313bbe4dfad0c2555d3b0c719ba6811fb6a361b8f110c967b50ea1b8e33969fa and analysis-view SHA-256 3ed591f99a6fa614d7275912bdfa0c626f88a58df340179cb6aac2157b29067d. The actual browser rendered eight checker candidates through the existing shared Results Viewer.

The cube request used 4HPwATDgc/ABMA:cAngAAAAAAAE with null dice. It produced analysis key sha256-c7239f1e7b935f2dd81fc6e41fae1d8e4924a7cdcebe1b5af474af0ba79b5f65 and analysis-view SHA-256 1b7c0f5d6392443a499d19e16e87afd6e89a74c522717d9bda7da6a6e643520e. The actual browser rendered all three cube actions through the same shared viewer.

Both inputs differ from the accepted K001 golden checker and cube GNUIDs. Neither accepted golden analysis was submitted to an engine.

## Cache/reuse proof

The browser submitted the same normalized checker request a second time. Node returned the same analysis key, the Analyzer observed the Node cache-hit state, the native-execution count stayed at one, and the materialized factual view retained the same SHA-256. Analyzer contains no independent deduplication layer.

## Shared viewer and browser boundary

Both completed Node views mounted through BMSAnalysisResults.renderNodeAnalysisView in site/assets/bs-analysis-results.js. Each product result contained exactly one data-bs-shared-analysis-presentation marker. No second Results Viewer or presentation contract was created.

The browser performs form validation, same-origin JSON submission/status polling, UI state changes, and shared-viewer mounting only. It does not invoke Node or GNU, parse raw GNU output, calculate moves/equities, or receive private runtime paths. Invalid incomplete GNUID input reached the invalid state before submission and created no presentation.

## Validation disposition

- Focused Analyzer JavaScript and Python contracts: PASS.
- Existing Results Viewer regression contracts: PASS.
- Actual headless browser proof over /analyze/: PASS, with live checker, live cube, Node cache reuse, zero page errors, and zero console errors.
- Full Quarto development render: PASS, 28/28 pages.
- Rendered static UI audit: PASS, 29 pages and zero findings.
- git diff --check from the authorized base through the implementation commit: PASS.
- Comprehensive entrypoint: environment-blocked at preflight because Rscript is not installed. Its available build/static components were run separately and passed.
- Full unit discovery: 215 tests, one failure and three skips. The only failure is the pre-existing publication-identity scanner debt.
- Quick gate: 80 tests, one failure and two skips. The only failure is the same pre-existing scanner debt. Its base and Task 011 finding maps are exactly equal across the same four historical paths.
- Generic human UX and generic live-browser procedures: not run; the task-specific actual browser product proof was run.

Machine-readable result SHA-256: 940455fe920527dc94ef160bcac36cd0f081144db92e4836c6d53a157e08f402

No D1, Corpus, Canonical Parquet, benchmark, Cloudflare production routing, production commissioning, authentication, quota, lease, multi-host scheduling, Explainer, comparison, board-editor, XGID/OGID conversion, or broad-polish work was performed.
