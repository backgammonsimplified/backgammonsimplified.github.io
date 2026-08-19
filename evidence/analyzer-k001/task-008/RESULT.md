# Analyzer K001 Task 008 materialization result

Date: 2026-08-19 EDT

Status: `COMPLETE — AWAITING INDEPENDENT ACCEPTANCE`

Task: `materialize-accepted-node-lesson-records-from-canonical-parquet-v1`

Starting implementation head:
`f53b2e1df917561141dbfcf3dca7d077639041d1`

Checkpoint: the commit containing this result on
`agent/analyzer-results-viewer-fixture-v1` / PR #15. No follow-on equivalence
work is included.

## Input authority and validation

The immutable packages were copied read-only over the verified
WSL -> Neotame -> HFCS gateway from the committed Canonical storage root. Both
packages passed their complete `SHA256SUMS.txt` inventories, manifest binding,
`_COMMITTED` binding, immutable-publication flag, reconciliation status,
contract status, relation-part inventory, and exact source-record inventory.

Checker authority:

- package: `1a38c5a48214a4ea156d1896b8ea09bcdce75880077fabb2fc516c5685ff259c`
- manifest: `bcd84099792e5679dd997ea4aa85f0d3ee217f5df79b2adc989b5938c6d2988e`
- committed checksum inventory: `88c8e805c16fcb177c6bea7a6210de892042bf3e9fa29c2a7804c88904a4fff1`
- source dataset: `sha256-2ea4a860090fecb6b51cc1d933b6ad678bddd278478089e21df14b68ccba5c39`
- exact source records: accepted checker
  `sha256-52e8ef0da2e4090a81f0ab726370811812c20f76f31730c5e6d132e63b774f3d`
  and excluded older cube
  `sha256-ba87405bf38017214424d71b1e3d1299ed323101db8893f2aa430054167a6414`

Accepted Learn cube authority:

- package: `bde4011fa40a384168a49529db7192e039a15252d4a2ab481c7b2fecfa98806b`
- manifest: `dbe6bcb41ac8ecdb52ffa33a72cc97bc47fae9c0f9bc67a9bc8559c197c2d11a`
- committed checksum inventory: `01109d1026a6ac1687a267eafe331bedb52507729f30a99cb4d35d386ed147c4`
- source dataset: `sha256-b4065495bb3e4e33895512779b47ee16272f78710801c756896c78039f731d3e`
- exact and sole source record:
  `sha256-1217f65d4a2c203e2370edb860ffaba81090a42f69d2a5fb56f5cceb64389e01`

Selection fails closed on any package-directory identity, manifest, committed
marker, checksum, record-inventory, duplicate-row, relation, occurrence kind,
presentation GNU identity, candidate evaluation, rank, or excluded-ID mismatch.

## Exact Canonical selection

Accepted checker:

- decision:
  `8e8e9519d238e20fdbb550ec871f3a6a8fb915fe0091353e1ad20e73cb21acb3`
- source occurrence/context:
  `740d6026d00939a9989d21c9f778f6397b343490e48f746a2b05a61f9d5cd8b6`
- decision position:
  `c9add1cd142dc640e1809cc0fc9fcf0f7f693d1afa2a79f7cb5867887978de1e`
- candidate IDs in source rank order:
  `cebe056b9fba14bb3a4fd58aa8f3e3d5430d98045ff21850c994bd24add37745`,
  `44f91cbe042d6b615184f62d32d59337e3a35f709b875f11958bfdc2bf421477`,
  `2940ef714c8cff1a3895543725738b43d64264c425968c3448c0a251a0e1542d`,
  `5fd8fc14885e320a36c7769bf3127c2662c3d9f3164418872c7696be426460c8`,
  `3c03cda00d76d9fbb7acc6d54dc78d2079fee4c1f10c946e4b2f3b8866a0027b`,
  `09806fcf119b0f5742865fd64f987cecc00a28338b429a89a8098aacca864cf0`,
  `6a2d4cbf49af863c3ca425061a616d836ef10e80429714fba0829180d2ec5837`,
  `96d18ebbdcf54e9eb07265464db5b9e2100c5c0c6ae6c46e90a8a3a2258862d2`
- evaluation IDs in the same order:
  `5605283e44df8961a3931a026557e2ace2581ccf07624b9666a4222c5db999d5`,
  `f3dc8dacfde2f22459efdbbfe6dd672c72b33770b18a1cdc185de4432af0c3c2`,
  `cfac350058eb00bc17fb7db3846ab6ebcd9500f6caab504eba7aadc8223b790a`,
  `25eacb7310df37fc276d02ae0a2fa681bacbfde27ba8ee3cc4d4e7550b83bb39`,
  `b5d56dae30b31d62a7d0edac69c6fe692d9ea7ad3f6ec60f01e65d28be3bacd2`,
  `445d1f6058fe6c6b13cb2340d8cd6bae358daf18d1d77b4a52a32e04a9a23cf4`,
  `0f45e065ab2ef6efde6bd9de08d12184120c1c568e35165944dd621a7c86a651`,
  `ab64cf96a489c8be46b74210b5037c3400415aadb269bb0385de4b313f4b7f53`
- result-position IDs: eight explicit nulls; reconstruction state is
  `not_available_from_source`, so none was invented.
- structured movement rows: eight explicit empty arrays. Existing build-time
  overlays are reused only after exact accepted-analysis, GNU-position, and
  move-text matching; browser code does not parse or apply moves.

Accepted Learn cube:

- cube occurrence:
  `215747e8305eff4e89325822fda7c967d2a242154194ff7a1b4b8ea6f34c5005`
- source occurrence/context:
  `e1c4f4aad95bb49b1a0c084c6efbc7172a4c66eb31f86b67d6dc1a92674c5ced`
- position:
  `16381b1bf9673c73b94d47d16df3ced8aa0bf252ed49f94fec1e8d9737eb7e7d`
- action IDs in source rank order:
  `5134e196c229cf5b7b36ce230fe26eedbb75ab8e1851010d6316008c233cfa0f`,
  `7ace038e9967b27f4c954b1a9b813f991f963e054e3994d6796d3cfd4c27a936`,
  `b0b5a1bdb5eebe7e4dd2ead2e48b22827ff870401381fe21a6f4d3eb0308e1ad`

## DuckDB/read-set and materialization evidence

The query texts are checked-in constants. Their deterministic identities are:

- checker selection: `25c917caf3e9bb919ab8caf0bba1f60dd8612741704785fb8dc22da51d993d69`
- checker evaluations: `803a1362dcb2f2f1fbb4c3d6d9756abbf5ebc5da4377086c1465938aa97d2e81`
- cube selection: `8cc545762708495f9f02103a6a501bf9c113f33e460dfd27af9e7cb621b9c70a`
- cube actions: `bc421f49566150b0608066649d2cfab01bda9457e6d3bb1df194df2c0482028b`
- excluded-cube selection: `d00e1db3d8852d6608676ad1c0e679cf83a83b88b659a0706bb66f8bfcfe26d2`
- excluded-cube actions: `347985693071e6b4b3d67ce00402ebdc5e9e7a39a79faedfbec6db4c184c6dca`

The configuration identity is
`4693f079aa6228bd7d5e8349063e8ee4b781d82c2c19ca81930d061600e909eb`.
Materialization hashes:

- checker semantic read set:
  `7a9de2204ecacbefb19cbc4c18188504fc6979a9c0bd46b2f76e52ed6d418cdb`
- checker analysis-view document:
  `9f1bca861fd52e5a9aacf18fb67f541e53a786e8511c416346bfa12c3122443c`
- cube semantic read set:
  `3d0176636402a97aea237d6126f988c6b98ff1f44b5645747512782fb585c0d1`
- cube analysis-view document:
  `535c1444450b9bc673a8303937f9a24c148af53cafc8091b3f50c1ebceebed6e`
- combined accepted golden-pair analysis-view JSON:
  `7af39183ca9e5f696d0fe3d4ce1e4729b58f4a95489d910490c6b16e1b4bb404`

The committed JSON evidence files are sufficient to repeat
`analysis_view_materializer.py` byte-for-byte without the browser or an engine.
The full external relation inventories and hashes are in
`materialization-evidence.json`.

## Excluded cube rejection

The excluded Package A cube was resolved only to prove rejection:

- source occurrence:
  `c0675948cf652adedae1083218040efca87237dfabca24d90a2252e6e3e6e7f0`
- cube occurrence:
  `602583121061add28c9a8ac41f452ab6baead4b47928b9876adc5bdcf560d9ad`
- position:
  `27f405cb778a5f880d2ecab5992a4be7d5d2d5a059835c096bbe0fa78ac25cbb`
- action IDs:
  `e8f846b4c106e0804a73fe913378aa97812919f081b5ef691984ce4d61f8fb9b`,
  `e843546c3ded127498f61d65495692cf494ce8b284bbfda06d7168c40f4eaa51`,
  `38fc590dad9634b4b67036231a90b94bf3faab0fa98d882bd0dae00d830977ea`
- disposition: `rejected-before-materialization`

The materializer checks that the excluded analysis key is byte-absent from the
combined viewer document and that the document contains exactly the two
accepted analysis keys.

## Provenance preservation

The semantic read sets and each analysis-view `canonical_context` retain equal
structured provenance objects, including source record/path/hash and line,
raw-block hash, GNU IDs, parser status/warnings/schema, source manifests,
producer repository/PR/commit, Node producer base/execution source, engine
version/executable/runtime, model/resource hashes, configuration hash, exact
options, invocation identity, parser identity/implementation/commit, and
Canonical writer commit/compression/PyArrow version.

Key identities include:

- producer identity:
  `b785713f755b9059dd7187ff07aec7a47372ccb393f7bd026a60acf7550f1cbf`
- configuration:
  `375b0cbf77d6a2e9961c2a25c8b957f28278582728089510496b55d38383ea01`
- invocation: `gnubg-cli-command-file-windows-v1`
- parser: `gnu-text-parser-v1`, Engine Kit commit
  `5dd21daf166f6284c0224ac35a4a5495cb00a0ff`
- Node materializer commit:
  `fb6a121474517c29b66d959d579a9282a61280b2`
- Canonical writer commit:
  `1569284972239a2627de8e5176eb47caef454fda`

Unavailable lexical, normalized, played-move, result-position, structured
movement, and row-local cube-depth states remain explicit null/empty values.

## Results Viewer consumption

The existing lesson data URL now contains the Canonical-derived pair. Both
existing Learn hosts select the immutable accepted analysis keys, the cube host
selects the exact Canonical action IDs, and `bs-lesson-analysis.js` delegates to
the existing `bs-analysis-results.js` shared presentation API. No second
renderer, browser-side Parquet access, raw GNU parsing, move application, or
analytical recalculation was added. The Node-direct document is retained under
the explicit local-authoring filename for presentation-sidecar use and the
separately gated future equivalence task.

## Validation

- immutable package checksum inventories: PASS for both packages;
- Canonical complete-family DuckDB intake: PASS, no gaps;
- deterministic materialization repeated against the immutable packages: PASS;
- excluded Package A substitution as the Learn cube package: rejected with
  manifest mismatch, exit 1;
- complete Python discovery: 196 tests PASS, 3 environment skips;
- focused viewer and lesson JavaScript: PASS;
- `bash scripts/testing/quick.sh`: PASS;
  - quick build/source/unit gate: PASS;
  - existing rendered-site representative audit: 16 pages, 0 findings;
  - UX helper syntax/source contracts: PASS;
  - live-browser automation: NOT RUN (requires served site/controller);
  - human UX: NOT RUN.
- `git diff --check`: PASS.

No GNU or Node analysis was rerun. Canonical Parquet was not mutated. Task
`validate-node-direct-parquet-analysis-equivalence-v1` was not started and
remains behind independent acceptance of this checkpoint.
