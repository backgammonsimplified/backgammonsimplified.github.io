# Analyzer K001 Task 009 semantic equivalence result

Status: `PASS`

Task: `validate-node-direct-parquet-analysis-equivalence-v1`

Starting implementation head: `d65f5a7931a41d681c63fd3f8fde6b6f41ddf0e6`

## Outcome

- Checker semantic equivalence: `PASS`
- Cube semantic equivalence: `PASS`
- Required factual mismatches: `0`
- Required provenance/identity mapping: `AUDITABLE`
- Deterministic repeated result: `PASS`
- Machine-readable result SHA-256: `ed8d97b1de56a190f08751a5ce158b98066f26d11aa61673cac50ca549b55368`

The comparison uses exact native numbers and strings. It applies no numeric tolerance, rounded-display comparison, generic text normalization, or missing-value backfill.

## Classification totals

| Classification | Count |
|---|---:|
| `EQUAL` | 281 |
| `SEMANTICALLY_NEUTRAL_REPRESENTATION_DIFFERENCE` | 148 |
| `EXPLICITLY_UNAVAILABLE_ON_ONE_SIDE` | 159 |
| `MISMATCH` | 0 |

## Bound inputs

| Input | SHA-256 |
|---|---|
| `tests/fixtures/node-k001-checker-analysis-view.json` | `0186d761a54a8e1f38a91686d960224790a3232efab487f8dc723bb390d8f1cf` |
| `tests/fixtures/node-k001-cube-analysis-view.json` | `dcb9888fc9846fc53fb86fdd733228b02acfea281d44a7798025bdaf248dd3a0` |
| `site/data/analyzer-node-k001-local-authoring-preview.json` | `89aba0db5a0431b8ce150c51fe903a8c79a51a24d4feacdd765b1bfd4c589f5e` |
| `scripts/analysis/node-k001-regression-authoring.json` | `1bab3a09031294dc598b44b774c4b0300a5274916cfc2d4a883a4e58ef3e3e9c` |
| `evidence/analyzer-k001/task-008/checker-read-set.json` | `7a9de2204ecacbefb19cbc4c18188504fc6979a9c0bd46b2f76e52ed6d418cdb` |
| `evidence/analyzer-k001/task-008/cube-read-set.json` | `3d0176636402a97aea237d6126f988c6b98ff1f44b5645747512782fb585c0d1` |
| `evidence/analyzer-k001/task-008/materialization-evidence.json` | `8c1545c202930efe325d4d5aabe609f33f864a22b38ecd665d82dbc4ca552975` |
| `site/data/analyzer-node-k001-lesson-preview.json` | `7af39183ca9e5f696d0fe3d4ce1e4729b58f4a95489d910490c6b16e1b4bb404` |
| `scripts/analysis/node-k001-canonical-materialization.json` | `4693f079aa6228bd7d5e8349063e8ee4b781d82c2c19ca81930d061600e909eb` |

## Legitimate representation differences

- Node uses a local sequential move ID while Canonical adds a stable content/relationship hash; order and native move text provide the explicit mapping.
  Fields: `checker.checker.candidate[1].candidate_identity`, `checker.checker.candidate[2].candidate_identity`, `checker.checker.candidate[3].candidate_identity`, `checker.checker.candidate[4].candidate_identity`, `checker.checker.candidate[5].candidate_identity`, `checker.checker.candidate[6].candidate_identity`, `checker.checker.candidate[7].candidate_identity`, `checker.checker.candidate[8].candidate_identity`.
- Node writes the best candidate's loss baseline as 0; Canonical represents the same best-row baseline with explicit null. Non-best losses remain exact native values.
  Fields: `checker.checker.candidate[1].difference_from_best`.
- Canonical evaluation source order is scoped within each candidate (one selected evaluation per candidate), while candidate rank/order is compared independently.
  Fields: `checker.checker.candidate[1].evaluation_source_order`, `checker.checker.candidate[2].evaluation_source_order`, `checker.checker.candidate[3].evaluation_source_order`, `checker.checker.candidate[4].evaluation_source_order`, `checker.checker.candidate[5].evaluation_source_order`, `checker.checker.candidate[6].evaluation_source_order`, `checker.checker.candidate[7].evaluation_source_order`, `checker.checker.candidate[8].evaluation_source_order`.
- Node separates evaluation mode and ply; Canonical's row label encodes the exact ply while producer options preserve mode='evaluation'.
  Fields: `checker.checker.candidate[1].evaluation_type`, `checker.checker.candidate[2].evaluation_type`, `checker.checker.candidate[3].evaluation_type`, `checker.checker.candidate[4].evaluation_type`, `checker.checker.candidate[5].evaluation_type`, `checker.checker.candidate[6].evaluation_type`, `checker.checker.candidate[7].evaluation_type`, `checker.checker.candidate[8].evaluation_type`.
- No rounded lexical loss is supplied on either side; Canonical keeps explicit null and the exact native difference is compared separately.
  Fields: `checker.checker.candidate[1].native_equity_loss_display`, `checker.checker.candidate[2].native_equity_loss_display`, `checker.checker.candidate[3].native_equity_loss_display`, `checker.checker.candidate[4].native_equity_loss_display`, `checker.checker.candidate[5].native_equity_loss_display`, `checker.checker.candidate[6].native_equity_loss_display`, `checker.checker.candidate[7].native_equity_loss_display`, `checker.checker.candidate[8].native_equity_loss_display`.
- Canonical expands Node's native equity label into an explicit Cubeful-equity semantic wrapper and selects that same native value for display.
  Fields: `checker.checker.candidate[1].native_equity_semantics`, `checker.checker.candidate[2].native_equity_semantics`, `checker.checker.candidate[3].native_equity_semantics`, `checker.checker.candidate[4].native_equity_semantics`, `checker.checker.candidate[5].native_equity_semantics`, `checker.checker.candidate[6].native_equity_semantics`, `checker.checker.candidate[7].native_equity_semantics`, `checker.checker.candidate[8].native_equity_semantics`.
- Only label capitalization changes; the exact native numeric equity is compared separately.
  Fields: `checker.checker.candidate[1].native_value_label`, `checker.checker.candidate[2].native_value_label`, `checker.checker.candidate[3].native_value_label`, `checker.checker.candidate[4].native_value_label`, `checker.checker.candidate[5].native_value_label`, `checker.checker.candidate[6].native_value_label`, `checker.checker.candidate[7].native_value_label`, `checker.checker.candidate[8].native_value_label`.
- Neither side supplies a normalized equity value: Node omits the field and Canonical retains explicit null without copying the native equity.
  Fields: `checker.checker.candidate[1].normalized_value`, `checker.checker.candidate[2].normalized_value`, `checker.checker.candidate[3].normalized_value`, `checker.checker.candidate[4].normalized_value`, `checker.checker.candidate[5].normalized_value`, `checker.checker.candidate[6].normalized_value`, `checker.checker.candidate[7].normalized_value`, `checker.checker.candidate[8].normalized_value`.
- Canonical names the unavailable normalized-equity slot but leaves its value null; it does not derive or copy a value from Node-direct evidence.
  Fields: `checker.checker.candidate[1].normalized_value_semantics`, `checker.checker.candidate[2].normalized_value_semantics`, `checker.checker.candidate[3].normalized_value_semantics`, `checker.checker.candidate[4].normalized_value_semantics`, `checker.checker.candidate[5].normalized_value_semantics`, `checker.checker.candidate[6].normalized_value_semantics`, `checker.checker.candidate[7].normalized_value_semantics`, `checker.checker.candidate[8].normalized_value_semantics`.
- Canonical expands the source field name with 'or_better'/'or_worse'; the native probability and player-on-roll perspective are unchanged.
  Fields: `checker.checker.candidate[1].probabilities.lose_gammon_or_worse`, `checker.checker.candidate[1].probabilities.win_gammon_or_better`, `checker.checker.candidate[2].probabilities.lose_gammon_or_worse`, `checker.checker.candidate[2].probabilities.win_gammon_or_better`, `checker.checker.candidate[3].probabilities.lose_gammon_or_worse`, `checker.checker.candidate[3].probabilities.win_gammon_or_better`, `checker.checker.candidate[4].probabilities.lose_gammon_or_worse`, `checker.checker.candidate[4].probabilities.win_gammon_or_better`, `checker.checker.candidate[5].probabilities.lose_gammon_or_worse`, `checker.checker.candidate[5].probabilities.win_gammon_or_better`, `checker.checker.candidate[6].probabilities.lose_gammon_or_worse`, `checker.checker.candidate[6].probabilities.win_gammon_or_better`, `checker.checker.candidate[7].probabilities.lose_gammon_or_worse`, `checker.checker.candidate[7].probabilities.win_gammon_or_better`, `checker.checker.candidate[8].probabilities.lose_gammon_or_worse`, `checker.checker.candidate[8].probabilities.win_gammon_or_better`, `checker.probabilities.position_probabilities.lose_gammon_or_worse`, `checker.probabilities.position_probabilities.win_gammon_or_better`, `cube.probabilities.position_probabilities.lose_gammon_or_worse`, `cube.probabilities.position_probabilities.win_gammon_or_better`.
- Canonical explicitly marks the sole exported evaluation for each complete Node candidate as the display row.
  Fields: `checker.checker.candidate[1].selected_for_display`, `checker.checker.candidate[2].selected_for_display`, `checker.checker.candidate[3].selected_for_display`, `checker.checker.candidate[4].selected_for_display`, `checker.checker.candidate[5].selected_for_display`, `checker.checker.candidate[6].selected_for_display`, `checker.checker.candidate[7].selected_for_display`, `checker.checker.candidate[8].selected_for_display`.
- Node analysis-view v0 omits unavailable structured movement; Canonical preserves the same unavailability as an explicit empty array and does not invent movement facts.
  Fields: `checker.checker.candidate[1].structured_movements`, `checker.checker.candidate[2].structured_movements`, `checker.checker.candidate[3].structured_movements`, `checker.checker.candidate[4].structured_movements`, `checker.checker.candidate[5].structured_movements`, `checker.checker.candidate[6].structured_movements`, `checker.checker.candidate[7].structured_movements`, `checker.checker.candidate[8].structured_movements`.
  Contract evidence: Node fixture limitation states that structured movement steps are absent; Task 008 checker read set requires [].
- Canonical names the presentation-support state explicitly; the retained Node projection represents the same state by supplying the exact candidate board overlay.
  Fields: `checker.checker.candidate[1].supported`, `checker.checker.candidate[2].supported`, `checker.checker.candidate[3].supported`, `checker.checker.candidate[4].supported`, `checker.checker.candidate[5].supported`, `checker.checker.candidate[6].supported`, `checker.checker.candidate[7].supported`, `checker.checker.candidate[8].supported`.
- Canonical supplies a presentation label for the same exact occurrence kind.
  Fields: `checker.context.decision_label`, `cube.context.decision_label`.
- Canonical adds a stable hashed relational identity; the Node source remains mapped by exact analysis/source-record identity rather than byte-equal wrapper IDs.
  Fields: `checker.identity.canonical_decision_id_wrapper`, `checker.identity.canonical_logical_position_id_wrapper`, `checker.identity.canonical_source_occurrence_id_wrapper`, `cube.identity.canonical_decision_id_wrapper`, `cube.identity.canonical_logical_position_id_wrapper`, `cube.identity.canonical_source_occurrence_id_wrapper`.
- Node-direct records one requested decision kind; Canonical preserves the containing producer configuration's decision-kind list, which includes that exact kind.
  Fields: `checker.provenance.settings.decision_types`, `cube.provenance.settings.decision_types`.
- Canonical stores the exact parser-warning subset as a JSON string; Node-direct also carries presentation warnings in its surrounding array.
  Fields: `checker.provenance.source.parser_warnings_json`, `cube.provenance.source.parser_warnings_json`.
- The retained Node comparison artifact and Canonical source envelope expose different named schema layers; the exact source record and producer identity bind them.
  Fields: `checker.provenance.source.source_schema_version`, `cube.provenance.source.source_schema_version`.
- Neither source contract states a separate requested cubeful flag; Canonical uses explicit null and actual/effective cubeful state is compared through producer options.
  Fields: `checker.settings.requested_cubeful`, `cube.settings.requested_cubeful`.
- Node encodes requested depth as a named setting and Canonical exposes the exact integer depth.
  Fields: `checker.settings.requested_ply`, `cube.settings.requested_ply`.
- The Node 'quick' authoring alias maps to the frozen one-ply profile; Canonical checker names the producer profile while the cube read set names its Canonical projection profile.
  Fields: `checker.settings.requested_profile`, `cube.settings.requested_profile`.
- Node uses the normalized action token as its local ID while Canonical adds a stable action hash; exact action meaning and source order bind the mapping.
  Fields: `cube.cube.action[1].action_identity`, `cube.cube.action[2].action_identity`, `cube.cube.action[3].action_identity`.
- The source emitted no cube-action difference value; Node omits the field and Canonical retains explicit null.
  Fields: `cube.cube.action[1].native_difference`, `cube.cube.action[2].native_difference`, `cube.cube.action[3].native_difference`.
- Canonical expands Node's equity label into an explicit source-native cube-equity wrapper and selects that same native value for display.
  Fields: `cube.cube.action[1].native_equity_semantics`, `cube.cube.action[2].native_equity_semantics`, `cube.cube.action[3].native_equity_semantics`.
- Only label capitalization changes; the exact source-native numeric equity is compared separately.
  Fields: `cube.cube.action[1].native_value_label`, `cube.cube.action[2].native_value_label`, `cube.cube.action[3].native_value_label`.
- Neither side supplies a normalized cube equity: Node omits it and Canonical preserves explicit null without copying native equity.
  Fields: `cube.cube.action[1].normalized_equity`, `cube.cube.action[2].normalized_equity`, `cube.cube.action[3].normalized_equity`.
- Canonical names the unavailable normalized cube-equity slot and explicitly states that no value was supplied; it does not copy the native equity.
  Fields: `cube.cube.action[1].normalized_equity_semantics`, `cube.cube.action[2].normalized_equity_semantics`, `cube.cube.action[3].normalized_equity_semantics`.
- Neither side claims a played/observed cube action; Canonical encodes the absent native and normalized forms as explicit nulls.
  Fields: `cube.cube.observed_action`.

## Explicit unavailable facts

- Node analysis-view v0 preserves the complete GNUID but does not separately project this occurrence-context field; Canonical preserves it without modifying the GNU identity.
  Fields: `checker.context.cube`, `checker.context.player_on_roll`, `checker.context.score`, `cube.context.cube`, `cube.context.player_on_roll`, `cube.context.score`.
  Contract evidence: Node fixture limitations: score and cube-state presentation fields are not represented separately; source_request.position.id remains exact.
- Relational occurrence context is not a field in Node analysis-view v0; native GNU identity is compared separately.
  Fields: `checker.context.relational_game_id`, `checker.context.relational_historical_pipeline_selected`, `checker.context.relational_match_id`, `cube.context.relational_game_id`, `cube.context.relational_historical_pipeline_selected`, `cube.context.relational_match_id`.
  Contract evidence: bms-node-analysis-view-v0 source_request contract; Canonical source_occurrence contract.
- The Canonical read-set adapter identity exists only after Parquet materialization.
  Fields: `checker.provenance.adapter`, `cube.provenance.adapter`.
  Contract evidence: tests/fixtures/node-k001-*-analysis-view.json (bms-node-analysis-view-v0); canonical_provenance retains the downstream source envelope without backfilling the Node artifact.
- Node analysis-view v0 retains the producer digest but not the producer repository/runtime/resource expansion bound by that digest.
  Fields: `checker.provenance.producer.analysis_producer_identity.configuration.configuration_hash`, `checker.provenance.producer.analysis_producer_identity.configuration.invocation_identity`, `checker.provenance.producer.analysis_producer_identity.configuration.model_or_weights_identity`, `checker.provenance.producer.analysis_producer_identity.configuration.options.beavers`, `checker.provenance.producer.analysis_producer_identity.configuration.options.deterministic`, `checker.provenance.producer.analysis_producer_identity.configuration.options.jacoby`, `checker.provenance.producer.analysis_producer_identity.configuration.options.move_filter`, `checker.provenance.producer.analysis_producer_identity.configuration.options.node_producer_base_commit`, `checker.provenance.producer.analysis_producer_identity.configuration.options.node_producer_version`, `checker.provenance.producer.analysis_producer_identity.configuration.options.noise`, `checker.provenance.producer.analysis_producer_identity.configuration.options.output_digits`, `checker.provenance.producer.analysis_producer_identity.configuration.options.output_mwc`, `checker.provenance.producer.analysis_producer_identity.configuration.options.output_winpc`, `checker.provenance.producer.analysis_producer_identity.configuration.options.platform_runtime_identity`, `checker.provenance.producer.analysis_producer_identity.configuration.options.runtime_executable_sha256`, `checker.provenance.producer.analysis_producer_identity.configuration.options.threads`, `checker.provenance.producer.analysis_producer_identity.configuration.options.variation`, `checker.provenance.producer.analysis_producer_identity.configuration.profile`, `checker.provenance.producer.analysis_producer_identity.node_producer.base_commit`, `checker.provenance.producer.analysis_producer_identity.node_producer.execution_source`, `checker.provenance.producer.analysis_producer_identity.node_producer.execution_source_sha256`, `checker.provenance.producer.analysis_producer_identity.node_producer.package_name`, `checker.provenance.producer.analysis_producer_identity.node_producer.package_version`, `checker.provenance.producer.analysis_producer_identity.node_producer.version`, `checker.provenance.producer.analysis_producer_identity.parser.implementation`, `checker.provenance.producer.analysis_producer_identity.parser.package_version`, `checker.provenance.producer.analysis_producer_identity.parser.source_commit`, `checker.provenance.producer.analysis_producer_identity.producer.executable_sha256`, `checker.provenance.producer.analysis_producer_identity.producer.platform_runtime_identity`, `checker.provenance.producer.analysis_producer_identity.producer.version_build`, `checker.provenance.producer.analysis_producer_identity.resources`, `checker.provenance.producer.analysis_producer_identity.schema_version`, `checker.provenance.producer.branch`, `checker.provenance.producer.commit`, `checker.provenance.producer.materializer.branch`, `checker.provenance.producer.materializer.commit`, `checker.provenance.producer.materializer.package_name`, `checker.provenance.producer.materializer.package_version`, `checker.provenance.producer.materializer.pr`, `checker.provenance.producer.materializer.repository`, `checker.provenance.producer.pr`, `checker.provenance.producer.repository`, `cube.provenance.producer.analysis_producer_identity.configuration.configuration_hash`, `cube.provenance.producer.analysis_producer_identity.configuration.invocation_identity`, `cube.provenance.producer.analysis_producer_identity.configuration.model_or_weights_identity`, `cube.provenance.producer.analysis_producer_identity.configuration.options.beavers`, `cube.provenance.producer.analysis_producer_identity.configuration.options.deterministic`, `cube.provenance.producer.analysis_producer_identity.configuration.options.jacoby`, `cube.provenance.producer.analysis_producer_identity.configuration.options.move_filter`, `cube.provenance.producer.analysis_producer_identity.configuration.options.node_producer_base_commit`, `cube.provenance.producer.analysis_producer_identity.configuration.options.node_producer_version`, `cube.provenance.producer.analysis_producer_identity.configuration.options.noise`, `cube.provenance.producer.analysis_producer_identity.configuration.options.output_digits`, `cube.provenance.producer.analysis_producer_identity.configuration.options.output_mwc`, `cube.provenance.producer.analysis_producer_identity.configuration.options.output_winpc`, `cube.provenance.producer.analysis_producer_identity.configuration.options.platform_runtime_identity`, `cube.provenance.producer.analysis_producer_identity.configuration.options.runtime_executable_sha256`, `cube.provenance.producer.analysis_producer_identity.configuration.options.threads`, `cube.provenance.producer.analysis_producer_identity.configuration.options.variation`, `cube.provenance.producer.analysis_producer_identity.configuration.profile`, `cube.provenance.producer.analysis_producer_identity.node_producer.base_commit`, `cube.provenance.producer.analysis_producer_identity.node_producer.execution_source`, `cube.provenance.producer.analysis_producer_identity.node_producer.execution_source_sha256`, `cube.provenance.producer.analysis_producer_identity.node_producer.package_name`, `cube.provenance.producer.analysis_producer_identity.node_producer.package_version`, `cube.provenance.producer.analysis_producer_identity.node_producer.version`, `cube.provenance.producer.analysis_producer_identity.parser.implementation`, `cube.provenance.producer.analysis_producer_identity.parser.package_version`, `cube.provenance.producer.analysis_producer_identity.parser.source_commit`, `cube.provenance.producer.analysis_producer_identity.producer.executable_sha256`, `cube.provenance.producer.analysis_producer_identity.producer.platform_runtime_identity`, `cube.provenance.producer.analysis_producer_identity.producer.version_build`, `cube.provenance.producer.analysis_producer_identity.resources`, `cube.provenance.producer.analysis_producer_identity.schema_version`, `cube.provenance.producer.branch`, `cube.provenance.producer.commit`, `cube.provenance.producer.materializer.branch`, `cube.provenance.producer.materializer.commit`, `cube.provenance.producer.materializer.package_name`, `cube.provenance.producer.materializer.package_version`, `cube.provenance.producer.materializer.pr`, `cube.provenance.producer.materializer.repository`, `cube.provenance.producer.pr`, `cube.provenance.producer.repository`.
  Contract evidence: tests/fixtures/node-k001-*-analysis-view.json (bms-node-analysis-view-v0); canonical_provenance retains the downstream source envelope without backfilling the Node artifact.
- Node analysis-view v0 does not separately expose this frozen producer configuration field.
  Fields: `checker.provenance.settings.configuration_identity`, `checker.provenance.settings.invocation_identity`, `checker.provenance.settings.model_or_weights_identity`, `checker.provenance.settings.options.beavers`, `checker.provenance.settings.options.deterministic`, `checker.provenance.settings.options.jacoby`, `checker.provenance.settings.options.move_filter`, `checker.provenance.settings.options.node_producer_base_commit`, `checker.provenance.settings.options.node_producer_version`, `checker.provenance.settings.options.noise`, `checker.provenance.settings.options.output_digits`, `checker.provenance.settings.options.output_mwc`, `checker.provenance.settings.options.output_winpc`, `checker.provenance.settings.options.platform_runtime_identity`, `checker.provenance.settings.options.runtime_executable_sha256`, `checker.provenance.settings.options.threads`, `checker.provenance.settings.options.variation`, `checker.provenance.settings.profile`, `cube.provenance.settings.configuration_identity`, `cube.provenance.settings.invocation_identity`, `cube.provenance.settings.model_or_weights_identity`, `cube.provenance.settings.options.beavers`, `cube.provenance.settings.options.deterministic`, `cube.provenance.settings.options.jacoby`, `cube.provenance.settings.options.move_filter`, `cube.provenance.settings.options.node_producer_base_commit`, `cube.provenance.settings.options.node_producer_version`, `cube.provenance.settings.options.noise`, `cube.provenance.settings.options.output_digits`, `cube.provenance.settings.options.output_mwc`, `cube.provenance.settings.options.output_winpc`, `cube.provenance.settings.options.platform_runtime_identity`, `cube.provenance.settings.options.runtime_executable_sha256`, `cube.provenance.settings.options.threads`, `cube.provenance.settings.options.variation`, `cube.provenance.settings.profile`.
  Contract evidence: tests/fixtures/node-k001-*-analysis-view.json (bms-node-analysis-view-v0); canonical_provenance retains the downstream source envelope without backfilling the Node artifact.
- The Canonical spool/package source envelope is richer than the retained Node analysis-view v0 contract.
  Fields: `checker.provenance.source.dataset_id`, `checker.provenance.source.parser_status`, `checker.provenance.source.raw_block_sha256`, `checker.provenance.source.source_path`, `checker.provenance.source_manifests`, `cube.provenance.source.dataset_id`, `cube.provenance.source.parser_status`, `cube.provenance.source.raw_block_sha256`, `cube.provenance.source.source_path`, `cube.provenance.source_manifests`.
  Contract evidence: tests/fixtures/node-k001-*-analysis-view.json (bms-node-analysis-view-v0); canonical_provenance retains the downstream source envelope without backfilling the Node artifact.
- Canonical writer identity is downstream authority metadata and is not a field in Node analysis-view v0.
  Fields: `checker.provenance.writer.commit`, `checker.provenance.writer.compression`, `checker.provenance.writer.compression_level`, `checker.provenance.writer.pyarrow_version`, `checker.provenance.writer.repository`, `checker.provenance.writer.rows_per_shard`, `cube.provenance.writer.commit`, `cube.provenance.writer.compression`, `cube.provenance.writer.compression_level`, `cube.provenance.writer.pyarrow_version`, `cube.provenance.writer.repository`, `cube.provenance.writer.rows_per_shard`.
  Contract evidence: tests/fixtures/node-k001-*-analysis-view.json (bms-node-analysis-view-v0); canonical_provenance retains the downstream source envelope without backfilling the Node artifact.
- Node-direct exposes block/global effective depth, but Canonical intentionally leaves row-local cube-action depth null; the comparator does not backfill it. Requested and block depth are compared separately.
  Fields: `cube.cube.action[1].row_local_actual_ply`, `cube.cube.action[2].row_local_actual_ply`, `cube.cube.action[3].row_local_actual_ply`.
  Contract evidence: cube-read-set limitations[0]: row-local actual ply is absent; requested and block analysis ply remain 1.

## Required factual mismatches

None.

## Determinism

two independent in-memory builds compared byte-for-byte; output contains no clock, host, or mutable Git-head fields.

No GNU, Node analysis, DuckDB query, Canonical download, or Canonical mutation is performed by this comparator.
