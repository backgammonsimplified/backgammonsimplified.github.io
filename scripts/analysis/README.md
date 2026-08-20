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

The materializer uses DuckDB for Parquet inspection/querying.

## Commissioned Node golden pair

The accepted Node checker and Learn cube are materialized from two immutable,
committed Canonical package authorities with:

```bash
CANONICAL_CHECKER_PACKAGE=/path/to/canonical-analysis-v1-retained-1a38c... \
CANONICAL_CUBE_PACKAGE=/path/to/canonical-analysis-v1-retained-bde401... \
  bash scripts/analysis/materialize-accepted-node-pair.sh
```

The command verifies the exact package directory identity, manifest hash,
`_COMMITTED` binding, `SHA256SUMS.txt`, immutable/reconciliation status, exact
source-record inventory, and complete relation-part inventory before DuckDB
selection. It selects by the accepted Node analysis key and derives the
Canonical decision/candidate/evaluation/occurrence/action IDs from Parquet.
Package A's explicitly excluded cube is queried only for rejection evidence and
must not occur in the output.

The deterministic outputs are:

- semantic read sets and materialization evidence under
  `evidence/analyzer-k001/task-008/`;
- the shared-viewer document at
  `site/data/analyzer-node-k001-lesson-preview.json`.

The prior Node-direct projection remains at
`site/data/analyzer-node-k001-local-authoring-preview.json` as presentation
sidecar and future equivalence input. Its board URLs are accepted only after an
exact analysis/GNU identity and move match; no analytical value is read from
that sidecar. The Learn hosts continue to use the existing Results Viewer.

## Node-direct / Canonical semantic equivalence

The Task 009 comparator reads only the accepted committed Node fixtures and
Task 008 read sets/evidence. It does not invoke GNU, Node analysis, DuckDB, or a
Canonical writer:

```bash
.venv/bin/python scripts/analysis/validate_node_parquet_equivalence.py \
  --output-json evidence/analyzer-k001/task-009/equivalence-result.json \
  --output-markdown evidence/analyzer-k001/task-009/RESULT.md \
  --verify-repeat
```

Every compared field is classified as `EQUAL`,
`SEMANTICALLY_NEUTRAL_REPRESENTATION_DIFFERENCE`,
`EXPLICITLY_UNAVAILABLE_ON_ONE_SIDE`, or `MISMATCH`. Native numeric values use
exact equality with no tolerance or rounded-display fallback. The accepted
input hashes, package/manifest identities, excluded Package A cube, complete
candidate/action ordering, and provenance round trip all fail closed.

## Deterministic Analysis View materializer

The Analyzer-owned deterministic transformation is implemented in
`analysis_view_materializer.py`. Its checked input boundary is an explicit
`analyzer-analysis-view-read-set-v1` semantic read set. That boundary keeps
physical Canonical column names out of browser code and, until the exact Corpus
package is published, prevents this repository from guessing a Parquet mapping.

The materializer requires every semantic key, including keys whose value is
explicitly `null`. A missing key, duplicate JSON key, orphan evaluation,
ambiguous display evaluation, duplicate source order, unsupported decision
kind, or mismatched position identity fails closed. It preserves:

- canonical decision, logical position, and distinct source-occurrence IDs;
- match, game, score, cube, dice, and provenance context;
- requested analysis depth separately from row-local actual depth;
- source-native and normalized values plus their stated semantics;
- all checker candidates/evaluations in source order and resulting-position IDs;
- cube occurrence facts separately from the complete analytical action set;
- explicit null and unsupported states.

Output uses sorted keys, stable semantic ordering, UTF-8, two-space indentation,
no non-finite JSON numbers, and one trailing newline. Repeat-byte validation is
available directly:

```bash
.venv/bin/python scripts/analysis/analysis_view_materializer.py \
  tests/fixtures/analyzer-analysis-view-read-set-v1.json \
  --output /tmp/analyzer-analysis-view.json \
  --verify-repeat
```

The generic checked-in read set is synthetic mechanics proof. The Task 008
read sets under `evidence/analyzer-k001/task-008/` are deterministic projections
of the exact commissioned immutable packages; Canonical Parquet remains the
analytical authority.

## Retrieval/materializer workloads

`retrieval_workloads_v1.json` freezes the query meaning and ordering for
`AVR-001` through `AVR-015`. `run_retrieval_workloads.py` hashes those query
definitions and refuses a registry with missing, duplicate, or additional IDs.
It records package/profile identity, resolved canonical IDs or seed, query hash,
fresh-process versus process-warm classification, latency, throughput, result
count/hash, CPU, process peak RAM, files touched, and copy/move readback results.

Metrics unavailable from the current driver are recorded as structured
`unavailable` values. In particular, the semantic JSON proof driver cannot
observe Parquet row groups, partitions, pruning, physical rows/bytes scanned, or
DuckDB file-touch telemetry. Normal runs are explicitly classified with unknown
filesystem-cache state and are never described as OS-cold I/O.

Run all workloads on the minimal proof input with:

```bash
.venv/bin/python scripts/analysis/run_retrieval_workloads.py \
  --profile minimal-json=tests/fixtures/analyzer-analysis-view-read-set-v1.json \
  --output /tmp/analyzer-avr-report.json
```

Multiple `--profile PROFILE_ID=PATH` arguments use the same registry definitions
and query hashes. The current JSON driver proves harness mechanics only. A real
DuckDB/Parquet profile comparison and Canonical conformance claim require the
published Corpus package, its exact identity, a verified physical mapping, and
the repository-pinned DuckDB dependency.

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

The preview preserves the real retained 3-1 checker position, real GNU 4-ply candidate ranks/equities/probabilities, played move, recommendation, actual 4-ply candidate depth, and candidate result-position identities.

On Laptop 2, with the normal website checkout and a sibling Backgammonboard checkout, regenerate both the analysis-view JSON and Backgammonboard SVGs with one command:

```bash
cd "$HOME/Documents/backgammonsimplified.github.io"
bash scripts/analysis/render-retained-checker-preview.sh
```

Override the Backgammonboard checkout when necessary:

```bash
BACKGAMMONBOARD_REPO=/path/to/backgammonboard \
  bash scripts/analysis/render-retained-checker-preview.sh
```

The wrapper runs the deterministic Python projection and then `scripts/render_real_checker_assets.R`.

## Candidate board assets

Checker candidate board assets are generated locally/build-time with `backgammonboard`. The browser only swaps cached SVG files.

Current Backgammonboard requirements relevant to Analyzer:

- `board_moves()` receives ordered structured atomic movement, not source notation strings;
- move points are relative to the mover;
- `die` may be `NA` when a row should not receive limited die checking;
- `ggboard()` renders the factual before-position and overlays the supplied movement;
- `after_xgid`, when available, validates the applied checker layout and does not replace the displayed before-position;
- the current Backgammon Simplified presets are `board_colors("bs")` and `board_style("bs")`.

For the bounded retained preview, `scripts/render_real_checker_assets.R` converts its already-normalized simple point-to-point tokens into `board_moves()` rows, leaves die assignment unspecified where notation has collapsed it, applies the movements to one factual starting XGID, and validates the resulting checker arrangement against `analyzer-view.json`.

The generated candidate SVGs deliberately all use the same starting position. Each one differs only by the candidate movement overlay. The renderer also rewrites `PROVENANCE.txt` with the exact Backgammonboard commit used.

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

## Reusable local Node authoring loop

Completed local Node analysis artifacts can be attached to the existing Results
Viewer without waiting for Corpus or Parquet:

```text
completed Node analysis-view v0 artifact
-> strict local/build-time projection
-> existing analysis-view JSON contract
-> existing shared Results Viewer
-> optional marked Learn lesson host
```

Create a config using
`node-k001-regression-authoring.json` as the interface example, then run:

```bash
bash scripts/analysis/materialize-node-analysis.sh path/to/authoring.json
```

The config explicitly supplies:

- `authority: local-development-only` and a stable output `slug`;
- each artifact path, exact `analysis_id`, selected `kind`, and asset subdirectory;
- the analysis-view output path/public URL and the asset output path/public root;
- presentation-only labels and whether a cube responder board should be prepared;
- optional Learn bindings for regions delimited by
  `bs-local-node-analysis:<name>:start/end` comments.

Relative filesystem paths resolve from the repository root. Environment
variables and `~` are expanded for artifact and output paths. Set
`BACKGAMMONCALCULATOR_REPO` and/or `BACKGAMMONBOARD_REPO` when the corresponding
R packages need to be installed into `.r-library`; `R_BIN`, `RSCRIPT_BIN`, and
`LOCAL_NODE_R_LIBS_USER` remain overridable.

The command selects every analysis by exact key and decision kind, rejects
duplicate JSON keys and ambiguous row identity/order, projects deterministic
JSON, and renders boards in a staging directory before replacing the requested
asset directory. Simple point-to-point checker notation receives build-time
movement overlays through `backgammonboard::board_moves()`. Unsupported notation
is retained with an explicit missing overlay; it is never interpreted or
guessed. Cube responder assets are only created when the config explicitly asks
for them and the offered-double state can be prepared unambiguously.

The output retains the Node schema, analysis key, artifact SHA-256, full source
request, and full producer-provenance object under `local_authoring`. Both the
config and output say `local-development-only`; the command refuses a Canonical
status. It consumes completed artifacts only and never starts GNU or another
analysis engine. The K001 checker/cube files in `tests/fixtures/` are regression
inputs, not a new analytical run or authority source.
