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

The repository setup command installs the materializer dependency into the existing `.venv`:

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

Do not add a permanent mapping until the exact joined Canonical Parquet reference package is available and inspected.

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

Synthetic viewer fixtures remain the deliberate malformed/error/degraded-state test source. Real retained records are added as separate generated fixtures after canonical package intake.

## Candidate board assets

Checker candidate board assets are generated at build/materialization time with the accepted `backgammonboard` renderer. The browser only swaps cached SVG files.

`backgammonboard` does not parse GNU/source move notation. The materializer must therefore prefer canonical structured atomic checker movement when available:

```text
candidate starting position identity/XGID
+ ordered movement steps: from, to, die
+ optional canonical resulting-position XGID
        |
        v
backgammonboard::board_moves(from, to, die)
        |
        v
backgammonboard::ggboard(
  starting_xgid,
  moves = structured_moves,
  after_xgid = resulting_xgid,
  colors = board_colors("bs"),
  style = board_style("bs")
)
        |
        v
cached candidate SVG
```

`after_xgid` validates the applied checker layout. It does not replace the displayed starting position. This lets the candidate asset show the movement overlay on the decision position while checking agreement with the canonical result position.

If the canonical package supplies a resulting position but no unambiguous structured movement steps, the materializer may render the resulting position as a separate static result board, but it must not invent movement arrows or die assignment.

Before Canonical Parquet v1 freezes, Analyzer therefore benefits from explicit candidate movement fields equivalent to ordered atomic `from`, `to`, and optional `die` values, in addition to the candidate/result-position identities. Native move notation should remain separately preserved for display/audit.