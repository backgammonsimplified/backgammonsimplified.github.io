# Analyzer K001 Task 013 canonical consumer conformance result

Status: `COMPLETE`

Task: `validate-canonical-consumer-conformance-sweep-v1`

Product implementation remained unchanged at
`agent/analyzer-canonical-consumer-conformance-v1@e9062f351bd971d80438a480990e645ce1227a33`.
The commit containing this result is evidence-only; its exact published SHA is
recorded in the Task Management Codex result.

## Outcome

| Consumer | Status | Disposition |
|---|---|---|
| DuckDB query/materialization | `PASS` | Accepted package, query, ordering, identity, provenance, and explicit-null bindings remain exact |
| Analyzer analysis-view | `PASS` | 588 exact/contract-classified comparisons, zero factual mismatches, deterministic materialization |
| Learn shared Results Viewer | `PASS` | Desktop/mobile browser proof, exact source bytes, one shared presentation, and no-fallback denial all pass |
| Research | `NOT_APPLICABLE` | Current Research pages mount no canonical/materialized analysis or shared Results Viewer |
| Sage-vs-GNU | `NOT_APPLICABLE` | No accepted current release/canonical consumer exists; the governed snapshot is pending and the active lane has no accepted immutable pair |
| Explainer canonical query/input | `PASS` | Accepted foreign-owned query contract preserves source-neutral joins, stable IDs, provenance, and external sidecar boundaries |

Required factual mismatches: `0`.

Unclassified mismatches: `0`.

Foreign-owner blockers: `0`.

## Refreshed prerequisite and exact authority

The live refresh established:

- Control Tower `master@386a9581ed380e112f8f9e04baebce7d8504875a` still names
  `validate-canonical-producer-conformance-sweep-v1` as the consumer sweep's
  sole dependency;
- Task Management Analyzer authority is
  `milestone/analyzer-k001@1c89e90a05a0bce11cce817becdeba2686fef5a6`;
- the producer result is read from
  `milestone/retcorpus-k001@46bd16fffc4c8850329cd55d17b892e23715de58`,
  SHA-256
  `ce34115768f3f7d29564abcb38a832026b8fdc7e1656113e5ef2362d06d4290d`,
  and remains `COMPLETE / CLEARED`;
- the accepted producer implementation branch still resolves to
  `feature/canonical-ingestion-listener-v0@5c15f3c957bbf5ee33dc7471a7e5230270b70b1c`.

Control Tower's task files still carry their planning-state metadata, but no
newer authority reverses the producer result. The current durable producer
report and Analyzer assignment explicitly clear the dependency gate.

## Accepted golden binding

Checker authority:

- package `1a38c5a48214a4ea156d1896b8ea09bcdce75880077fabb2fc516c5685ff259c`;
- manifest `bcd84099792e5679dd997ea4aa85f0d3ee217f5df79b2adc989b5938c6d2988e`;
- analysis `sha256-52e8ef0da2e4090a81f0ab726370811812c20f76f31730c5e6d132e63b774f3d`.

Cube authority:

- package `bde4011fa40a384168a49529db7192e039a15252d4a2ab481c7b2fecfa98806b`;
- manifest `dbe6bcb41ac8ecdb52ffa33a72cc97bc47fae9c0f9bc67a9bc8559c197c2d11a`;
- analysis `sha256-1217f65d4a2c203e2370edb860ffaba81090a42f69d2a5fb56f5cceb64389e01`.

The older Package A cube
`sha256-ba87405bf38017214424d71b1e3d1299ed323101db8893f2aa430054167a6414`
remains explicitly rejected before materialization. It is absent from the
accepted output.

The bound repository evidence is:

- `evidence/analyzer-k001/task-008/checker-read-set.json` —
  `7a9de2204ecacbefb19cbc4c18188504fc6979a9c0bd46b2f76e52ed6d418cdb`;
- `evidence/analyzer-k001/task-008/cube-read-set.json` —
  `3d0176636402a97aea237d6126f988c6b98ff1f44b5645747512782fb585c0d1`;
- `evidence/analyzer-k001/task-008/materialization-evidence.json` —
  `8c1545c202930efe325d4d5aabe609f33f864a22b38ecd665d82dbc4ca552975`;
- `evidence/analyzer-k001/task-009/equivalence-result.json` —
  `ed8d97b1de56a190f08751a5ce158b98066f26d11aa61673cac50ca549b55368`;
- `evidence/analyzer-k001/task-010/learn-consumption-result.json` —
  `596d4a4a4fd6f77d61099bb06791f9ff57a3d36579806f69b8bb4f0019ac53b7`;
- `site/data/analyzer-node-k001-lesson-preview.json` —
  `7af39183ca9e5f696d0fe3d4ce1e4729b58f4a95489d910490c6b16e1b4bb404`.

No Canonical package or accepted artifact was regenerated or mutated.

## Applicable consumers

### DuckDB and Analyzer

The checked-in DuckDB query hashes still bind the exact accepted selections,
evaluations, cube actions, excluded cube, and native-rank ordering. The Task 008
read sets reproduce the checked-in analysis view byte-for-byte and retain the
full package/source/writer provenance envelope.

The Task 009 comparator was executed twice, with its own two-build repeat check
enabled on each execution. Both machine results are byte-identical at
`ed8d97b1de56a190f08751a5ce158b98066f26d11aa61673cac50ca549b55368`.
The 588 comparisons classify as 281 equal, 148 existing field-contract
representation differences, 159 explicitly unavailable on one side, and zero
mismatches. No tolerance, generic normalization, inferred fact, or missing-value
backfill is used.

### Learn

The existing Task 010 proof was executed twice against a fresh 28-page render.
Each execution performs two complete source/runtime builds. Chromium
139.0.7258.5 loaded the checker and cube at desktop/mobile sizes, fetched the
exact canonical-derived bytes, exposed the eight checker candidates and three
cube actions in their accepted order, and mounted exactly one existing shared
Results Viewer presentation.

The bounded 404 control mounted no presentation and made zero requests for the
retained local-authoring source. Both runs produced identical machine evidence
SHA-256
`c0d4d5451a116de1ad0abc7e27a6d4d05a36e12034d8b47ebe8711a27724d27a`.

### Explainer

The foreign-owned repository was inspected read-only at
`feature/explainer-feature-v2-k002@011e347cea73ae9c01d00700eaea9c5149993229`.
Its accepted `explainer-canonical-parquet-query-patterns-v1` boundary opens all
ten Canonical relations as read-only DuckDB views, joins evaluations by both
candidate and source-occurrence provenance, uses stable Canonical IDs rather
than physical row order, and keeps feature/split/model/explanation data in
external sidecars.

The 12 focused canonical-query/model-output contract tests passed twice. Their
negative controls reject a redefined canonical input contract and unsafe
external relation names. No Explainer code, modeling artifact, or sidecar was
modified.

## Not-applicable consumers

Research is not silently called a pass: the current Research source tree has no
analysis-view/shared-viewer mount. Its relevant JavaScript presentation tests,
fresh render, and publication-page contracts pass, but there is no current
canonical consumer boundary.

Sage-vs-GNU is likewise not silently called a pass. Its website release reader
reports `pending` with 15 governed snapshot files absent; the current page has
no canonical/shared-viewer mount. Task Management records the active benchmark
lane as blocked before an accepted immutable pair and the post-match lane as
waiting for that pair. A future accepted canonicalized output is the trigger
for a later consumer check; it is not a Task 013 blocker.

## Negative controls and determinism

All meaningful applicable controls pass:

- wrong package/manifest binding;
- excluded older cube substitution;
- candidate reorder and exact native-equity drift;
- missing-to-null or cube-depth backfill;
- local-authoring fallback;
- shared-viewer bypass;
- Explainer canonical-contract redefinition and unsafe sidecar relation name.

The substantive conformance proof was repeated. Equivalence, Learn runtime, and
Explainer contract results match across both runs. The machine result contains
no timestamp, host-local path, duration, or other volatile semantic field.

## Validation

- focused Python consumer contracts: 80 pass, one environment-inapplicable skip;
- focused JavaScript Analyzer/Results Viewer/Learn/Research contracts: pass;
- equivalence proof twice: pass, 588 comparisons, zero mismatches, byte-identical;
- Learn browser proof twice: pass, positive and no-fallback controls, byte-identical;
- Explainer focused tests twice: 12/12 pass on each run;
- Quarto development render: 28/28 pages pass;
- rendered glossary and static UI audit: pass, 29 pages, zero findings;
- complete Python discovery: 211 pass, one historical scanner failure, three skips;
- quick build gate: JavaScript phases pass; 82 Python tests pass, the same one
  historical scanner failure remains, and one test is skipped;
- `git diff --check`: pass.

The only aggregate failure is the accepted historical publication-identity
scanner debt in Task 009 evidence and its comparator. Those accepted files were
not rewritten merely to silence the scanner.

## Boundaries

```text
Canonical writes: NONE
golden GNU/Node/Sage engine rerun: NO
second Results Viewer or presentation contract: NO
benchmark workstream mutation: NONE
Prompt 012 execution: NO
foreign repository mutation: NONE
remaining issue: none
```
