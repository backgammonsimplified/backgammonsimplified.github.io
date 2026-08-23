# Task 018 reference and provenance inventory

All references were inspected read-only before implementation. No reference
repository was modified.

## Accepted website base

Repository: `backgammonsimplified/backgammonsimplified.github.io`

Commit: `5014338360fe4bd0aab13ea56bc2a54f63a99a25`

Inspected paths:

- `site/analyze/index.qmd`
- `site/includes/analyzer-form.html`
- `site/assets/bs-analyzer-live.js`
- `site/assets/bs-analysis-results.js`
- `shiny/position-dashboard/app.R`
- `shiny/position-dashboard/readme.md`
- `evidence/analyzer-k001/task-011/RESULT.md`
- `evidence/analyzer-k001/task-011/interactive-position-node-loop-result.json`
- `evidence/analyzer-k001/task-016/RESULT.md`
- `evidence/analyzer-k001/task-016/server-request-lookup-result.json`
- `tests/test_analyzer_live.js`
- `tests/test_analyzer_live_browser.py`
- `tests/test_analyzer_local_preview.py`
- `tests/test_analyzer_server_browser.py`
- `tests/test_analysis_results_viewer.js`

The Shiny dashboard was treated only as the retained project-owned XGID
preview/display surface. It was not reused as a second Analyzer application.

## Private project references

Repository: `backgammonsimplified/backgammon-private`

Commit: `c9c56567a55f0751b95414a115aa0901023ad855`

Inspected paths:

- `good zips/opengammon-position-editor-capture.zip`
  - `README.md`, `NOTICE.md`, `LICENSE`, `VALIDATION.md`, and
    `notes/ui-inventory.md` inside the archive
- `good zips/hedgehog-ui-capture.zip`
  - `README.md`, `PROVENANCE.md`, `NOTICE.md`, `LICENSE`, `VALIDATION.md`,
    `notes/live-extraction-status.md`, and `clean-room/editor.js` inside the
    archive
- `archive/20260729-123300-CT-TASKS-03-LONG-BACKLOG/20260729-123300-CT-TASKS-03-LONG-BACKLOG/tasks/prototype-client-side-board-editor-v1.md`

These real retained artifacts were present despite the earlier literal-name
inventory note. Both archives distinguish independently authored clean-room
MIT-licensed UI studies from unlicensed third-party capture output. Task 018
used only the clean-room interaction inventory as a design reference. It
copied no OpenGammon or Hedgehog captured source, branding, or assets.

## Board/rendering semantics

Repository: `backgammonsimplified/backgammonboard`

Commit: `e3a989788758d30a0be065490d29ec48a88a05c0`

Inspected paths:

- `R/gnuid-input.R`
- `R/position.R`
- `R/match-info.R`
- `R/cube-state.R`
- `R/dice.R`
- `R/perspective.R`
- `R/xgid.R`
- `dev/render-gnuid-roundtrip-gallery.R`

This reference confirmed that complete GNUID conversion belongs to
`backgammoncalculator`; renderer orientation is presentation-only.

## Identifier/state semantics

Repository: `backgammonsimplified/backgammoncalculator`

Commit: `a385a963ed01a6eac083dae7a1b246b1c150b3eb`

Inspected paths:

- `R/position_identifiers.R`
- `inst/GNUID_XGID_ATTRIBUTION.md`
- `inst/THIRD_PARTY_NOTICES.md`
- `inst/extdata/identifier_regressions.csv`
- `inst/extdata/gnu_4ply_identifier_oracle.csv`

The browser codec ports the accepted stable-player physical-point mapping,
bars/off counts, little-endian GNU Base64 layout, dice owner, cube, score,
match length, Crawford/Jacoby, validation, and complete GNUID normalization.
It implements no speculative XGID or OGID codec. The accepted calculator
notices attribute GNUID/XGID bit-field concepts to MIT-licensed `bglab`; the
browser source retains that provenance comment.

## Node request authority

Repository: `backgammonsimplified/backgammon-node`

Commit: `acc1e3ae44a71b18438d048d810294701ad1ed73`

Inspected paths:

- `docs/architecture/SERVICE_CONTRACTS.md`
- `src/backgammon_node/contracts.py`
- `tests/test_contracts.py`

Task 018 retains the accepted submission-v2 schema, complete GNUID-only positions,
checker dice, cube null dice, GNU / 1-ply, and the existing Node-owned request,
identity, queue, execution, and result semantics.
