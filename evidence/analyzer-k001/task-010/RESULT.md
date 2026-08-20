# Analyzer K001 Task 010 Learn consumption result

Status: `PASS`

Task: `prove-learn-consumption-from-server-derived-analysis-v1`
Starting implementation head: `c69b7a599baf2f8b88491110a95df7167a09cdd3`
Final implementation head: `79ef91292d06a5bc7846f5a49a4f3329071b7d7a`

## Product-path gates

| Gate | Result |
|---|---|
| `checker_learn_canonical_derived_consumption` | `PASS` |
| `cube_learn_canonical_derived_consumption` | `PASS` |
| `shared_results_viewer_consumption` | `PASS` |
| `server_derived_source_binding` | `PASS` |
| `negative_control_no_fallback_proof` | `PASS` |
| `excluded_cube_rejection` | `PASS` |
| `browser_presentation_only_boundaries` | `PASS` |
| `task_009_equivalence_binding` | `PASS` |
| `runtime_browser_proof` | `PASS` |

Required product-path blockers: `0`

## Auditable lineage

- Learn document SHA-256: `7af39183ca9e5f696d0fe3d4ce1e4729b58f4a95489d910490c6b16e1b4bb404`
- Checker package / manifest: `1a38c5a48214a4ea156d1896b8ea09bcdce75880077fabb2fc516c5685ff259c` / `bcd84099792e5679dd997ea4aa85f0d3ee217f5df79b2adc989b5938c6d2988e`
- Cube package / manifest: `bde4011fa40a384168a49529db7192e039a15252d4a2ab481c7b2fecfa98806b` / `dbe6bcb41ac8ecdb52ffa33a72cc97bc47fae9c0f9bc67a9bc8559c197c2d11a`
- Task 009 equivalence SHA-256: `ed8d97b1de56a190f08751a5ce158b98066f26d11aa61673cac50ca549b55368` (`PASS`, zero factual mismatches)
- Machine-readable result SHA-256: `596d4a4a4fd6f77d61099bb06791f9ff57a3d36579806f69b8bb4f0019ac53b7`

## Runtime and negative control

Chromium loaded both rendered Learn routes at desktop and mobile sizes. Each page requested the exact Canonical-derived URL and received bytes matching the accepted Learn document hash. The checker exposed eight accepted candidate IDs and its recommendation; the cube exposed three accepted action IDs and its recommendation through the shared Results Viewer marker.

A separate bounded server denied that URL for both routes. Both hosts showed their load error, mounted no analysis/shared presentation, and made zero requests for the retained local-authoring document.

The browser sources are presentation-only: same-origin JSON fetch -> existing lesson adapter -> existing shared Results Viewer. Narrow source checks reject Parquet/DuckDB, subprocess/analysis-engine, raw GNU decoding/parsing, and Node-direct fallback boundaries.

## Determinism

two complete source/runtime builds compared byte-for-byte; no clock, host, port, duration, or mutable Git lookup is recorded.

No GNU, Node analysis, DuckDB query, Canonical download, or Canonical mutation was performed.
