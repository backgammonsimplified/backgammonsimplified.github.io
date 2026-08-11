# Analyzer canonical-data materialization

The browser does not read Parquet directly.

The intended boundary is:

```text
Canonical Analysis Parquet v1
-> deterministic local/build-time materializer
-> analysis-view JSON
-> existing Results Viewer
```

Parquet remains authoritative analytical storage. The generated JSON is a rebuildable consumer projection.

## Dependency

The repository setup command installs the Python materializer dependency into the existing `.venv`:

```bash
bash scripts/setup/windows-dev.sh
```

The materializer currently uses DuckDB for Parquet inspection/querying.

## Reference-package intake

Before writing a field mapping for a new canonical package, inspect it without guessing producer semantics:

```bash
.venv/Scripts/python.exe scripts/analysis/inspect_canonical_parquet.py \
  /path/to/canonical/v1 \
  --require-complete-family \
  --output /path/to/intake-report.json
```

The inspector recognizes the accepted logical family:

```text
positions
games
decisions
candidates
evaluations
exclusions
manifest.json
```

It records table files, SHA-256 values, row counts, and DuckDB-observed column names/types. Missing logical tables are reported explicitly. It does not infer aliases, synthesize missing values, or reinterpret source-native numeric fields.

## Mapping rule

Do not add a permanent Canonical Parquet mapping until the exact joined reference package is available and inspected.

The retained-data proof must preserve at minimum:

- position/context and checker dice;
- source family/provenance;
- requested depth separately from actual evaluation-row depth;
- checker rank/order and candidate/result-position identity when supplied;
- established native/normalized values and outcome probabilities;
- played move versus analytical recommendation when supplied;
- observed cube action versus analytical recommendation when supplied;
- null/missing/unsupported source fields;
- documented XGID representational limitations.

Cube rows must not receive an invented row-local actual depth when the retained source does not provide one.

Synthetic viewer fixtures remain the deliberate malformed/error/degraded-state test source.

## Interim retained checker preview

Until the joined Canonical Parquet reference package is published, the Analyzer preview uses the already accepted retained checker fixture at:

```text
fixtures/real-analysis/checker-sage-gnu-disagreement-001/
```

The deterministic projection command is:

```bash
.venv/Scripts/python.exe \
  scripts/analysis/project_retained_checker_preview.py
```

That writes:

```text
site/data/analyzer-retained-checker-preview.json
```

The preview preserves the real retained 3-1 checker position, real GNU 4-ply candidate ranks/equities/probabilities, played move, recommendation, actual 4-ply candidate depth, and candidate result-position identities.

## Candidate board assets

Checker candidate board assets are generated locally/build-time with `backgammonboard`. The browser only swaps cached SVG files.

Current Backgammonboard requirements relevant to Analyzer:

- `board_moves()` receives ordered structured atomic movement, not source notation strings;
- move points are relative to the mover;
- `die` may be `NA` when a row should not receive limited die checking;
- `ggboard()` renders the factual before-position and overlays the supplied movement;
- `after_xgid`, when available, validates the applied checker layout and does not replace the displayed before-position;
- the current Backgammon Simplified presets are `board_colors("bs")` and `board_style("bs")`.

For the bounded retained preview, `scripts/render_real_checker_assets.R` converts its already-normalized simple point-to-point tokens into `board_moves()` rows, leaves die assignment unspecified where the notation has collapsed it, applies the movements to one factual starting XGID, and validates the resulting checker arrangement against `analyzer-view.json`.

On Laptop 2, with a sibling Backgammonboard checkout, regenerate the starting board and all three candidate overlays with:

```bash
cd "$HOME/Documents/backgammonsimplified.github.io"

Rscript scripts/render_real_checker_assets.R \
  fixtures/real-analysis/checker-sage-gnu-disagreement-001 \
  site/data/checker-sage-gnu-disagreement-001.json \
  "$HOME/Documents/backgammonboard" \
  site/assets/positions/real-analysis/checker-sage-gnu-disagreement-001
```

The generated candidate SVGs deliberately all use the same starting position. Each one differs only by the candidate movement overlay. Their movement application is checked against the retained resulting-position arrangement before the SVG is accepted.

For Canonical Parquet v1, the preferred durable path is stronger and avoids notation parsing entirely:

```text
candidate starting position identity/XGID
+ ordered movement steps: from, to, optional die
+ canonical resulting-position identity/XGID when available
        |
        v
backgammonboard::board_moves(...)
        |
        v
backgammonboard::ggboard(starting_position, moves = structured_moves, ...)
        |
        v
cached candidate SVG
```

If Canonical Parquet supplies a resulting position but no unambiguous structured movement steps, the materializer may render a separate resulting position, but it must not invent movement arrows or die assignment. Analyzer therefore benefits from explicit ordered checker movement fields in Canonical Parquet in addition to native notation and candidate/result-position identities.
