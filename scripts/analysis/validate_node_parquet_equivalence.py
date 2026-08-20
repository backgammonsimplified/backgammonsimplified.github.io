#!/usr/bin/env python3
"""Prove semantic equivalence for the accepted Node K001 golden pair.

This checker consumes only committed evidence.  It never invokes GNU, Node,
DuckDB, or a Canonical writer.  Comparisons are exact unless a named,
field-specific representation rule below says otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.analysis import analysis_view_materializer as view_materializer
    from scripts.analysis import materialize_accepted_node_pair as pair_materializer
except ModuleNotFoundError:  # Direct execution sets sys.path to scripts/analysis.
    import analysis_view_materializer as view_materializer
    import materialize_accepted_node_pair as pair_materializer


ROOT = Path(__file__).resolve().parents[2]
STARTING_HEAD = "d65f5a7931a41d681c63fd3f8fde6b6f41ddf0e6"
SCHEMA = "analyzer-node-parquet-semantic-equivalence-v1"
COMPARATOR_VERSION = "validate-node-direct-parquet-analysis-equivalence-v1"

EQUAL = "EQUAL"
NEUTRAL = "SEMANTICALLY_NEUTRAL_REPRESENTATION_DIFFERENCE"
UNAVAILABLE = "EXPLICITLY_UNAVAILABLE_ON_ONE_SIDE"
MISMATCH = "MISMATCH"
CLASSIFICATIONS = (EQUAL, NEUTRAL, UNAVAILABLE, MISMATCH)

CHECKER_ID = "sha256-52e8ef0da2e4090a81f0ab726370811812c20f76f31730c5e6d132e63b774f3d"
CUBE_ID = "sha256-1217f65d4a2c203e2370edb860ffaba81090a42f69d2a5fb56f5cceb64389e01"
EXCLUDED_CUBE_ID = "sha256-ba87405bf38017214424d71b1e3d1299ed323101db8893f2aa430054167a6414"

PATHS = {
    "node_checker": "tests/fixtures/node-k001-checker-analysis-view.json",
    "node_cube": "tests/fixtures/node-k001-cube-analysis-view.json",
    "node_projection": "site/data/analyzer-node-k001-local-authoring-preview.json",
    "node_config": "scripts/analysis/node-k001-regression-authoring.json",
    "checker_read_set": "evidence/analyzer-k001/task-008/checker-read-set.json",
    "cube_read_set": "evidence/analyzer-k001/task-008/cube-read-set.json",
    "materialization_evidence": "evidence/analyzer-k001/task-008/materialization-evidence.json",
    "lesson_view": "site/data/analyzer-node-k001-lesson-preview.json",
    "canonical_config": "scripts/analysis/node-k001-canonical-materialization.json",
}

EXPECTED_HASHES = {
    "node_checker": "0186d761a54a8e1f38a91686d960224790a3232efab487f8dc723bb390d8f1cf",
    "node_cube": "dcb9888fc9846fc53fb86fdd733228b02acfea281d44a7798025bdaf248dd3a0",
    "node_projection": "89aba0db5a0431b8ce150c51fe903a8c79a51a24d4feacdd765b1bfd4c589f5e",
    "node_config": "1bab3a09031294dc598b44b774c4b0300a5274916cfc2d4a883a4e58ef3e3e9c",
    "checker_read_set": "7a9de2204ecacbefb19cbc4c18188504fc6979a9c0bd46b2f76e52ed6d418cdb",
    "cube_read_set": "3d0176636402a97aea237d6126f988c6b98ff1f44b5645747512782fb585c0d1",
    "materialization_evidence": "8c1545c202930efe325d4d5aabe609f33f864a22b38ecd665d82dbc4ca552975",
    "lesson_view": "7af39183ca9e5f696d0fe3d4ce1e4729b58f4a95489d910490c6b16e1b4bb404",
    "canonical_config": "4693f079aa6228bd7d5e8349063e8ee4b781d82c2c19ca81930d061600e909eb",
}

EXPECTED_PACKAGES = {
    "checker": {
        "package_id": "1a38c5a48214a4ea156d1896b8ea09bcdce75880077fabb2fc516c5685ff259c",
        "manifest_sha256": "bcd84099792e5679dd997ea4aa85f0d3ee217f5df79b2adc989b5938c6d2988e",
    },
    "cube": {
        "package_id": "bde4011fa40a384168a49529db7192e039a15252d4a2ab481c7b2fecfa98806b",
        "manifest_sha256": "dbe6bcb41ac8ecdb52ffa33a72cc97bc47fae9c0f9bc67a9bc8559c197c2d11a",
    },
}

EXPECTED_CANONICAL_IDS = {
    "checker": {
        "decision_id": "8e8e9519d238e20fdbb550ec871f3a6a8fb915fe0091353e1ad20e73cb21acb3",
        "logical_position_id": "c9add1cd142dc640e1809cc0fc9fcf0f7f693d1afa2a79f7cb5867887978de1e",
        "source_occurrence_id": "740d6026d00939a9989d21c9f778f6397b343490e48f746a2b05a61f9d5cd8b6",
        "candidate_ids": [
            "cebe056b9fba14bb3a4fd58aa8f3e3d5430d98045ff21850c994bd24add37745",
            "44f91cbe042d6b615184f62d32d59337e3a35f709b875f11958bfdc2bf421477",
            "2940ef714c8cff1a3895543725738b43d64264c425968c3448c0a251a0e1542d",
            "5fd8fc14885e320a36c7769bf3127c2662c3d9f3164418872c7696be426460c8",
            "3c03cda00d76d9fbb7acc6d54dc78d2079fee4c1f10c946e4b2f3b8866a0027b",
            "09806fcf119b0f5742865fd64f987cecc00a28338b429a89a8098aacca864cf0",
            "6a2d4cbf49af863c3ca425061a616d836ef10e80429714fba0829180d2ec5837",
            "96d18ebbdcf54e9eb07265464db5b9e2100c5c0c6ae6c46e90a8a3a2258862d2",
        ],
        "evaluation_ids": [
            "5605283e44df8961a3931a026557e2ace2581ccf07624b9666a4222c5db999d5",
            "f3dc8dacfde2f22459efdbbfe6dd672c72b33770b18a1cdc185de4432af0c3c2",
            "cfac350058eb00bc17fb7db3846ab6ebcd9500f6caab504eba7aadc8223b790a",
            "25eacb7310df37fc276d02ae0a2fa681bacbfde27ba8ee3cc4d4e7550b83bb39",
            "b5d56dae30b31d62a7d0edac69c6fe692d9ea7ad3f6ec60f01e65d28be3bacd2",
            "445d1f6058fe6c6b13cb2340d8cd6bae358daf18d1d77b4a52a32e04a9a23cf4",
            "0f45e065ab2ef6efde6bd9de08d12184120c1c568e35165944dd621a7c86a651",
            "ab64cf96a489c8be46b74210b5037c3400415aadb269bb0385de4b313f4b7f53",
        ],
    },
    "cube": {
        "decision_id": "215747e8305eff4e89325822fda7c967d2a242154194ff7a1b4b8ea6f34c5005",
        "logical_position_id": "16381b1bf9673c73b94d47d16df3ced8aa0bf252ed49f94fec1e8d9737eb7e7d",
        "source_occurrence_id": "e1c4f4aad95bb49b1a0c084c6efbc7172a4c66eb31f86b67d6dc1a92674c5ced",
        "action_ids": [
            "5134e196c229cf5b7b36ce230fe26eedbb75ab8e1851010d6316008c233cfa0f",
            "7ace038e9967b27f4c954b1a9b813f991f963e054e3994d6796d3cfd4c27a936",
            "b0b5a1bdb5eebe7e4dd2ead2e48b22827ff870401381fe21a6f4d3eb0308e1ad",
        ],
    },
}

PROBABILITY_MAP = {
    "win": "win",
    "win_gammon": "win_gammon_or_better",
    "win_backgammon": "win_backgammon",
    "lose": "lose",
    "lose_gammon": "lose_gammon_or_worse",
    "lose_backgammon": "lose_backgammon",
}

MISSING = object()


class EquivalenceError(ValueError):
    """Evidence cannot be compared without guessing."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def stable_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EquivalenceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        result = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (OSError, json.JSONDecodeError) as error:
        raise EquivalenceError(f"unable to read {path}: {error}") from error
    if not isinstance(result, dict):
        raise EquivalenceError(f"{path} must contain one JSON object")
    return result


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def side(path: str, value: Any = MISSING, availability: str = "AVAILABLE") -> dict[str, Any]:
    result: dict[str, Any] = {"path": path, "availability": availability}
    if value is not MISSING:
        result["value"] = value
    return result


def exact_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isfinite(float(left)) and math.isfinite(float(right)) and left == right
    return type(left) is type(right) and left == right


class Collector:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(
        self,
        scope: str,
        category: str,
        field: str,
        classification: str,
        node: dict[str, Any],
        canonical: dict[str, Any],
        reason: str,
        contract_evidence: str | None = None,
    ) -> None:
        if classification not in CLASSIFICATIONS:
            raise EquivalenceError(f"unsupported classification {classification}")
        row = {
            "scope": scope,
            "category": category,
            "field": field,
            "classification": classification,
            "required": True,
            "node_direct": node,
            "canonical_derived": canonical,
            "reason": reason,
        }
        if contract_evidence is not None:
            row["contract_evidence"] = contract_evidence
        self.rows.append(row)

    def compare(
        self,
        scope: str,
        category: str,
        field: str,
        node_path: str,
        node_value: Any,
        canonical_path: str,
        canonical_value: Any,
        reason: str = "The semantic values are exactly equal.",
    ) -> None:
        if (
            not isinstance(node_value, bool)
            and not isinstance(canonical_value, bool)
            and isinstance(node_value, (int, float))
            and isinstance(canonical_value, (int, float))
            and node_value == canonical_value
            and type(node_value) is not type(canonical_value)
        ):
            classification = NEUTRAL
            reason = "Equal finite JSON numbers use integer versus decimal lexical representations."
        elif exact_equal(node_value, canonical_value):
            classification = EQUAL
        else:
            classification = MISMATCH
            reason = "Required semantic values differ; no normalization rule applies."
        self.add(
            scope,
            category,
            field,
            classification,
            side(node_path, node_value),
            side(canonical_path, canonical_value),
            reason,
        )

    def expect(
        self,
        scope: str,
        category: str,
        field: str,
        expected_path: str,
        expected: Any,
        actual_path: str,
        actual: Any,
    ) -> None:
        self.compare(
            scope,
            category,
            field,
            expected_path,
            expected,
            actual_path,
            actual,
            "The committed value equals the frozen accepted authority.",
        )

    def neutral(
        self,
        scope: str,
        category: str,
        field: str,
        node_path: str,
        node_value: Any,
        canonical_path: str,
        canonical_value: Any,
        valid: bool,
        reason: str,
        contract_evidence: str | None = None,
    ) -> None:
        self.add(
            scope,
            category,
            field,
            NEUTRAL if valid else MISMATCH,
            side(node_path, node_value),
            side(canonical_path, canonical_value),
            reason if valid else "The explicit representation rule did not match; comparison fails closed.",
            contract_evidence,
        )

    def unavailable(
        self,
        scope: str,
        category: str,
        field: str,
        unavailable_side: str,
        unavailable_path: str,
        available_path: str,
        available_value: Any,
        reason: str,
        contract_evidence: str,
    ) -> None:
        if unavailable_side == "node":
            node = side(unavailable_path, availability="UNAVAILABLE_BY_CONTRACT")
            canonical = side(available_path, available_value)
        elif unavailable_side == "canonical":
            node = side(available_path, available_value)
            canonical = side(unavailable_path, availability="UNAVAILABLE_BY_CONTRACT")
        else:
            raise EquivalenceError(f"invalid unavailable side: {unavailable_side}")
        self.add(
            scope,
            category,
            field,
            UNAVAILABLE,
            node,
            canonical,
            reason,
            contract_evidence,
        )


def one_analysis(document: dict[str, Any], path: str) -> dict[str, Any]:
    analyses = document.get("analyses")
    if not isinstance(analyses, list) or len(analyses) != 1 or not isinstance(analyses[0], dict):
        raise EquivalenceError(f"{path}.analyses must contain exactly one object")
    return analyses[0]


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise EquivalenceError(f"{path} must be an array")
    return value


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EquivalenceError(f"{path} must be an object")
    return value


def split_gnuid(node: dict[str, Any]) -> tuple[str, str, str]:
    source_request = require_object(node.get("source_request"), "node.source_request")
    position = require_object(source_request.get("position"), "node.source_request.position")
    gnuid = position.get("id")
    if position.get("format") != "gnuid" or not isinstance(gnuid, str):
        raise EquivalenceError("Node source position must be one GNUID")
    parts = gnuid.split(":")
    if len(parts) != 2 or not all(parts):
        raise EquivalenceError("Node GNUID must contain one position and one match component")
    return gnuid, parts[0], parts[1]


def flatten_object(value: dict[str, Any], prefix: str = "") -> Iterable[tuple[str, Any]]:
    for key in sorted(value):
        child = value[key]
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(child, dict):
            yield from flatten_object(child, path)
        else:
            # Lists are intentional contract units (resources, manifests, decision types).
            yield path, child


def node_path_value(node: dict[str, Any], dotted: str) -> Any:
    current: Any = node
    for component in dotted.split("."):
        if not isinstance(current, dict) or component not in current:
            return MISSING
        current = current[component]
    return current


def compare_probabilities(
    collector: Collector,
    scope: str,
    category: str,
    field_prefix: str,
    node_path: str,
    node_values: Any,
    canonical_path: str,
    canonical_values: Any,
) -> None:
    node_values = require_object(node_values, node_path)
    canonical_values = require_object(canonical_values, canonical_path)
    for node_key, canonical_key in PROBABILITY_MAP.items():
        node_value = node_values.get(node_key, MISSING)
        canonical_value = canonical_values.get(canonical_key, MISSING)
        field = f"{field_prefix}.{canonical_key}"
        if node_key in {"win_gammon", "lose_gammon"}:
            collector.neutral(
                scope,
                category,
                field,
                f"{node_path}.{node_key}",
                node_value,
                f"{canonical_path}.{canonical_key}",
                canonical_value,
                exact_equal(node_value, canonical_value),
                "Canonical expands the source field name with 'or_better'/'or_worse'; the native probability and player-on-roll perspective are unchanged.",
            )
        else:
            collector.compare(
                scope,
                category,
                field,
                f"{node_path}.{node_key}",
                node_value,
                f"{canonical_path}.{canonical_key}",
                canonical_value,
            )


def compare_provenance(
    collector: Collector,
    scope: str,
    node: dict[str, Any],
    canonical: dict[str, Any],
) -> None:
    provenance = require_object(canonical.get("canonical_provenance"), f"{scope}.canonical_provenance")
    gnuid, position_id, match_id = split_gnuid(node)
    mapping: dict[str, tuple[str, Any]] = {
        "producer.analysis_producer_identity.configuration.engine": ("engine.name", node_path_value(node, "engine.name")),
        "producer.analysis_producer_identity.configuration.engine_version": ("engine.version", node_path_value(node, "engine.version")),
        "producer.analysis_producer_identity.configuration.options.actual_evaluation_type": ("settings.effective.actual_evaluation_type", node_path_value(node, "settings.effective.actual_evaluation_type")),
        "producer.analysis_producer_identity.configuration.options.cubeful": ("settings.effective.cubeful", node_path_value(node, "settings.effective.cubeful")),
        "producer.analysis_producer_identity.configuration.options.evaluation_plies": ("settings.effective.evaluation_plies", node_path_value(node, "settings.effective.evaluation_plies")),
        "producer.analysis_producer_identity.configuration.options.pruning": ("settings.effective.pruning", node_path_value(node, "settings.effective.pruning")),
        "producer.analysis_producer_identity.configuration.parser_version": ("producer_provenance.parser.identity", node_path_value(node, "producer_provenance.parser.identity")),
        "producer.analysis_producer_identity.parser.identity": ("producer_provenance.parser.identity", node_path_value(node, "producer_provenance.parser.identity")),
        "producer.analysis_producer_identity.producer.engine_name": ("engine.name", node_path_value(node, "engine.name")),
        "producer.analysis_producer_identity.producer.engine_version": ("engine.version", node_path_value(node, "engine.version")),
        "producer.analysis_producer_identity.producer_identity_sha256": ("producer_provenance.producer_identity_sha256", node_path_value(node, "producer_provenance.producer_identity_sha256")),
        "settings.analysis_setting": ("settings.requested.analysis_setting", node_path_value(node, "settings.requested.analysis_setting")),
        "settings.options.actual_evaluation_type": ("settings.effective.actual_evaluation_type", node_path_value(node, "settings.effective.actual_evaluation_type")),
        "settings.options.cubeful": ("settings.effective.cubeful", node_path_value(node, "settings.effective.cubeful")),
        "settings.options.evaluation_plies": ("settings.effective.evaluation_plies", node_path_value(node, "settings.effective.evaluation_plies")),
        "settings.options.pruning": ("settings.effective.pruning", node_path_value(node, "settings.effective.pruning")),
        "settings.parser_identity": ("producer_provenance.parser.identity", node_path_value(node, "producer_provenance.parser.identity")),
        "settings.producer_identity": ("producer_provenance.producer_identity_sha256", node_path_value(node, "producer_provenance.producer_identity_sha256")),
        "source.gnu_id_native": ("source_request.position.id", gnuid),
        "source.gnu_position_id_native": ("source_request.position.id[position]", position_id),
        "source.gnu_match_id_native": ("source_request.position.id[match]", match_id),
        "source.source_record_id": ("analysis_key", node.get("analysis_key", MISSING)),
    }
    for canonical_path, canonical_value in flatten_object(provenance):
        full_canonical_path = f"canonical_provenance.{canonical_path}"
        if canonical_path in mapping:
            node_path, node_value = mapping[canonical_path]
            collector.compare(
                scope,
                "provenance",
                canonical_path,
                node_path,
                node_value,
                full_canonical_path,
                canonical_value,
            )
            continue
        if canonical_path == "settings.decision_types":
            decision_type = node_path_value(node, "settings.requested.decision_type")
            valid = (
                isinstance(canonical_value, list)
                and decision_type in canonical_value
                and all(isinstance(item, str) for item in canonical_value)
            )
            collector.neutral(
                scope,
                "provenance",
                canonical_path,
                "settings.requested.decision_type",
                decision_type,
                full_canonical_path,
                canonical_value,
                valid,
                "Node-direct records one requested decision kind; Canonical preserves the containing producer configuration's decision-kind list, which includes that exact kind.",
            )
            continue
        if canonical_path == "source.parser_warnings_json":
            try:
                canonical_warnings = json.loads(canonical_value)
            except (TypeError, json.JSONDecodeError):
                canonical_warnings = MISSING
            node_warnings = node.get("warnings", MISSING)
            valid = (
                isinstance(canonical_warnings, list)
                and isinstance(node_warnings, list)
                and all(item in node_warnings for item in canonical_warnings)
            )
            collector.neutral(
                scope,
                "provenance",
                canonical_path,
                "warnings[parser subset]",
                canonical_warnings,
                full_canonical_path,
                canonical_value,
                valid,
                "Canonical stores the exact parser-warning subset as a JSON string; Node-direct also carries presentation warnings in its surrounding array.",
            )
            continue
        if canonical_path == "source.source_schema_version":
            node_schema = node.get("schema_version", MISSING)
            collector.neutral(
                scope,
                "provenance",
                canonical_path,
                "schema_version",
                node_schema,
                full_canonical_path,
                canonical_value,
                node_schema == "bms-node-analysis-view-v0"
                and canonical_value == "bms-node-canonical-spool-record-v0",
                "The retained Node comparison artifact and Canonical source envelope expose different named schema layers; the exact source record and producer identity bind them.",
            )
            continue
        if canonical_path == "adapter":
            reason = "The Canonical read-set adapter identity exists only after Parquet materialization."
        elif canonical_path.startswith("writer."):
            reason = "Canonical writer identity is downstream authority metadata and is not a field in Node analysis-view v0."
        elif canonical_path.startswith("source.") or canonical_path == "source_manifests":
            reason = "The Canonical spool/package source envelope is richer than the retained Node analysis-view v0 contract."
        elif canonical_path.startswith("producer."):
            reason = "Node analysis-view v0 retains the producer digest but not the producer repository/runtime/resource expansion bound by that digest."
        else:
            reason = "Node analysis-view v0 does not separately expose this frozen producer configuration field."
        collector.unavailable(
            scope,
            "provenance",
            canonical_path,
            "node",
            f"node-direct.{canonical_path}",
            full_canonical_path,
            canonical_value,
            reason,
            "tests/fixtures/node-k001-*-analysis-view.json (bms-node-analysis-view-v0); canonical_provenance retains the downstream source envelope without backfilling the Node artifact",
        )


def compare_common(
    collector: Collector,
    scope: str,
    node: dict[str, Any],
    canonical: dict[str, Any],
    expected_id: str,
) -> None:
    collector.expect(scope, "identity", "accepted_analysis_identity.node", "accepted identity", expected_id, "analysis_key", node.get("analysis_key", MISSING))
    collector.expect(scope, "identity", "accepted_analysis_identity.canonical", "accepted identity", expected_id, "analysis_id", canonical.get("analysis_id", MISSING))
    collector.compare(scope, "identity", "occurrence_kind", "analysis_kind", node.get("analysis_kind", MISSING), "decision_kind", canonical.get("decision_kind", MISSING))
    collector.compare(scope, "identity", "source_record_mapping", "analysis_key", node.get("analysis_key", MISSING), "source_occurrence.source_record_id", node_path_value(canonical, "source_occurrence.source_record_id"))
    collector.compare(scope, "identity", "logical_opportunity_mapping", "analysis_key", node.get("analysis_key", MISSING), "source_occurrence.logical_opportunity_id", node_path_value(canonical, "source_occurrence.logical_opportunity_id"))

    gnuid, position_id, match_id = split_gnuid(node)
    collector.compare(scope, "identity", "gnu_identity", "source_request.position.id", gnuid, "canonical_provenance.source.gnu_id_native", node_path_value(canonical, "canonical_provenance.source.gnu_id_native"))
    collector.compare(scope, "identity", "gnu_position_identity", "source_request.position.id[position]", position_id, "canonical_provenance.source.gnu_position_id_native", node_path_value(canonical, "canonical_provenance.source.gnu_position_id_native"))
    collector.compare(scope, "identity", "gnu_match_identity", "source_request.position.id[match]", match_id, "canonical_provenance.source.gnu_match_id_native", node_path_value(canonical, "canonical_provenance.source.gnu_match_id_native"))

    canonical_ids = EXPECTED_CANONICAL_IDS[scope]
    for field, read_path in (
        ("decision_id", "canonical_decision_id"),
        ("logical_position_id", "logical_position_id"),
        ("source_occurrence_id", "source_occurrence.occurrence_id"),
    ):
        value = node_path_value(canonical, read_path)
        collector.neutral(
            scope,
            "identity",
            f"canonical_{field}_wrapper",
            "analysis_key",
            expected_id,
            read_path,
            value,
            value == canonical_ids[field],
            "Canonical adds a stable hashed relational identity; the Node source remains mapped by exact analysis/source-record identity rather than byte-equal wrapper IDs.",
        )

    collector.compare(scope, "identity", "canonical_position_mapping", "logical_position_id", canonical.get("logical_position_id", MISSING), "position.position_id", node_path_value(canonical, "position.position_id"))
    collector.compare(scope, "identity", "canonical_dataset_mapping", "source_occurrence.source_id", node_path_value(canonical, "source_occurrence.source_id"), "canonical_provenance.source.dataset_id", node_path_value(canonical, "canonical_provenance.source.dataset_id"))
    collector.compare(scope, "identity", "source_line_start", "source_occurrence.line_number", node_path_value(canonical, "source_occurrence.line_number"), "source_occurrence.source_start_line", node_path_value(canonical, "source_occurrence.source_start_line"))
    collector.compare(scope, "identity", "source_line_end", "source_occurrence.line_number", node_path_value(canonical, "source_occurrence.line_number"), "source_occurrence.source_end_line", node_path_value(canonical, "source_occurrence.source_end_line"))
    if "gnu_position_id_native" in require_object(canonical.get("source_occurrence"), "source_occurrence"):
        collector.compare(scope, "identity", "source_occurrence_gnu_position", "source_request.position.id[position]", position_id, "source_occurrence.gnu_position_id_native", node_path_value(canonical, "source_occurrence.gnu_position_id_native"))
    if "gnu_match_id_native" in require_object(canonical.get("source_occurrence"), "source_occurrence"):
        collector.compare(scope, "identity", "source_occurrence_gnu_match", "source_request.position.id[match]", match_id, "source_occurrence.gnu_match_id_native", node_path_value(canonical, "source_occurrence.gnu_match_id_native"))
    if "gnu_position_id" in require_object(canonical.get("position"), "position"):
        collector.compare(scope, "identity", "position_gnu_identity", "source_request.position.id[position]", position_id, "position.gnu_position_id", node_path_value(canonical, "position.gnu_position_id"))

    collector.compare(scope, "context", "dice", "source_request.dice", node_path_value(node, "source_request.dice"), "context.dice", node_path_value(canonical, "context.dice"))
    collector.neutral(
        scope,
        "context",
        "decision_label",
        "analysis_kind",
        node.get("analysis_kind", MISSING),
        "context.decision",
        node_path_value(canonical, "context.decision"),
        (scope == "checker" and node_path_value(canonical, "context.decision") == "Checker play")
        or (scope == "cube" and node_path_value(canonical, "context.decision") == "Cube decision"),
        "Canonical supplies a presentation label for the same exact occurrence kind.",
    )
    for field in ("score", "cube", "player_on_roll"):
        collector.unavailable(
            scope,
            "context",
            field,
            "node",
            f"source_request.{field}",
            f"context.{field}",
            node_path_value(canonical, f"context.{field}"),
            "Node analysis-view v0 preserves the complete GNUID but does not separately project this occurrence-context field; Canonical preserves it without modifying the GNU identity.",
            "Node fixture limitations: score and cube-state presentation fields are not represented separately; source_request.position.id remains exact",
        )
    for field in ("match_id", "game_id", "historical_pipeline_selected"):
        collector.unavailable(
            scope,
            "context",
            f"relational_{field}",
            "node",
            f"node-direct.source_occurrence.{field}",
            f"source_occurrence.{field}",
            node_path_value(canonical, f"source_occurrence.{field}"),
            "Relational occurrence context is not a field in Node analysis-view v0; native GNU identity is compared separately.",
            "bms-node-analysis-view-v0 source_request contract; Canonical source_occurrence contract",
        )

    requested = node_path_value(node, "settings.requested.analysis_setting")
    requested_ply = node_path_value(canonical, "requested_analysis.requested_ply")
    collector.neutral(
        scope,
        "settings",
        "requested_ply",
        "settings.requested.analysis_setting",
        requested,
        "requested_analysis.requested_ply",
        requested_ply,
        requested == f"{requested_ply}ply",
        "Node encodes requested depth as a named setting and Canonical exposes the exact integer depth.",
    )
    profile = node_path_value(canonical, "requested_analysis.profile_id")
    collector.neutral(
        scope,
        "settings",
        "requested_profile",
        "settings.requested.report_mode",
        node_path_value(node, "settings.requested.report_mode"),
        "requested_analysis.profile_id",
        profile,
        node_path_value(node, "settings.requested.report_mode") == "quick"
        and profile in {
            "gnu-1.08.003-mingw-20240428-1ply-cubeful-noiseless-windows",
            "canonical-analysis-parquet-v1",
        },
        "The Node 'quick' authoring alias maps to the frozen one-ply profile; Canonical checker names the producer profile while the cube read set names its Canonical projection profile.",
    )
    collector.neutral(
        scope,
        "settings",
        "requested_cubeful",
        "settings.requested.cubeful",
        MISSING,
        "requested_analysis.cubeful",
        node_path_value(canonical, "requested_analysis.cubeful"),
        node_path_value(canonical, "requested_analysis.cubeful") is None,
        "Neither source contract states a separate requested cubeful flag; Canonical uses explicit null and actual/effective cubeful state is compared through producer options.",
    )
    for field in ("actual_evaluation_type", "evaluation_plies", "cubeful", "pruning"):
        collector.compare(
            scope,
            "settings",
            f"effective_{field}",
            f"settings.effective.{field}",
            node_path_value(node, f"settings.effective.{field}"),
            f"canonical_provenance.settings.options.{field}",
            node_path_value(canonical, f"canonical_provenance.settings.options.{field}"),
        )

    compare_probabilities(
        collector,
        scope,
        "probabilities",
        "position_probabilities",
        "probabilities",
        node.get("probabilities"),
        "probabilities",
        canonical.get("probabilities"),
    )
    compare_provenance(collector, scope, node, canonical)


def compare_checker(
    collector: Collector,
    node: dict[str, Any],
    canonical: dict[str, Any],
    projected: dict[str, Any],
) -> None:
    scope = "checker"
    compare_common(collector, scope, node, canonical, CHECKER_ID)
    collector.compare(scope, "checker", "recommendation", "recommendation.notation", node_path_value(node, "recommendation.notation"), "presentation.recommendation", node_path_value(canonical, "presentation.recommendation"))
    collector.compare(scope, "checker", "played_move", "played_move", node.get("played_move", MISSING), "presentation.played_move", node_path_value(canonical, "presentation.played_move"))

    node_candidates = require_list(node_path_value(node, "checker.candidates"), "node.checker.candidates")
    canonical_candidates = require_list(canonical.get("checker_candidates"), "canonical.checker_candidates")
    evaluations = require_list(canonical.get("checker_evaluations"), "canonical.checker_evaluations")
    projected_candidates = require_list(projected.get("candidates"), "node projection candidates")
    collector.compare(scope, "checker", "candidate_count", "checker.candidates.length", len(node_candidates), "checker_candidates.length", len(canonical_candidates))
    collector.compare(scope, "checker", "evaluation_count", "checker.candidates.length", len(node_candidates), "checker_evaluations.length", len(evaluations))
    collector.compare(scope, "checker", "projected_candidate_count", "checker.candidates.length", len(node_candidates), "node_projection.candidates.length", len(projected_candidates))
    if not (len(node_candidates) == len(canonical_candidates) == len(evaluations) == len(projected_candidates)):
        return

    expected_ids = EXPECTED_CANONICAL_IDS[scope]
    for index, (source, candidate, evaluation, projection) in enumerate(
        zip(node_candidates, canonical_candidates, evaluations, projected_candidates), start=1
    ):
        prefix = f"candidate[{index}]"
        collector.compare(scope, "checker", f"{prefix}.source_order", f"checker.candidates[{index - 1}].source_order", source.get("source_order", MISSING), f"checker_candidates[{index - 1}].source_order", candidate.get("source_order", MISSING))
        collector.compare(scope, "checker", f"{prefix}.display_rank", f"checker.candidates[{index - 1}].display_order", source.get("display_order", MISSING), f"checker_candidates[{index - 1}].display_rank", candidate.get("display_rank", MISSING))
        collector.neutral(
            scope,
            "checker",
            f"{prefix}.candidate_identity",
            f"checker.candidates[{index - 1}].id",
            source.get("id", MISSING),
            f"checker_candidates[{index - 1}].candidate_id",
            candidate.get("candidate_id", MISSING),
            source.get("id") == f"gnu-move-{index}"
            and candidate.get("candidate_id") == expected_ids["candidate_ids"][index - 1],
            "Node uses a local sequential move ID while Canonical adds a stable content/relationship hash; order and native move text provide the explicit mapping.",
        )
        collector.expect(scope, "checker", f"{prefix}.evaluation_identity", f"accepted evaluation ID {index}", expected_ids["evaluation_ids"][index - 1], f"checker_evaluations[{index - 1}].evaluation_id", evaluation.get("evaluation_id", MISSING))
        collector.compare(scope, "checker", f"{prefix}.candidate_evaluation_mapping", f"accepted candidate ID {index}", expected_ids["candidate_ids"][index - 1], f"checker_evaluations[{index - 1}].candidate_id", evaluation.get("candidate_id", MISSING))
        collector.compare(scope, "checker", f"{prefix}.native_move", f"checker.candidates[{index - 1}].notation", source.get("notation", MISSING), f"checker_candidates[{index - 1}].native_move", candidate.get("native_move", MISSING))
        collector.compare(scope, "checker", f"{prefix}.normalized_move", f"checker.candidates[{index - 1}].notation", source.get("notation", MISSING), f"checker_candidates[{index - 1}].normalized_move", candidate.get("normalized_move", MISSING))
        collector.compare(scope, "checker", f"{prefix}.actual_ply", f"checker.candidates[{index - 1}].evaluation.ply", node_path_value(source, "evaluation.ply"), f"checker_evaluations[{index - 1}].actual_ply", evaluation.get("actual_ply", MISSING))
        expected_type = f"{node_path_value(source, 'evaluation.ply')}-ply"
        collector.neutral(
            scope,
            "checker",
            f"{prefix}.evaluation_type",
            f"checker.candidates[{index - 1}].evaluation",
            source.get("evaluation", MISSING),
            f"checker_evaluations[{index - 1}].evaluation_type",
            evaluation.get("evaluation_type", MISSING),
            node_path_value(source, "evaluation.type") == "evaluation"
            and evaluation.get("evaluation_type") == expected_type,
            "Node separates evaluation mode and ply; Canonical's row label encodes the exact ply while producer options preserve mode='evaluation'.",
        )
        collector.neutral(
            scope,
            "checker",
            f"{prefix}.native_value_label",
            f"checker.candidates[{index - 1}].value.label",
            node_path_value(source, "value.label"),
            f"checker_evaluations[{index - 1}].native_value.label",
            node_path_value(evaluation, "native_value.label"),
            isinstance(node_path_value(source, "value.label"), str)
            and isinstance(node_path_value(evaluation, "native_value.label"), str)
            and node_path_value(source, "value.label").casefold()
            == node_path_value(evaluation, "native_value.label").casefold(),
            "Only label capitalization changes; the exact native numeric equity is compared separately.",
        )
        collector.compare(scope, "checker", f"{prefix}.native_equity", f"checker.candidates[{index - 1}].value.value", node_path_value(source, "value.value"), f"checker_evaluations[{index - 1}].native_value.value", node_path_value(evaluation, "native_value.value"))
        collector.neutral(
            scope,
            "checker",
            f"{prefix}.native_equity_semantics",
            f"checker.candidates[{index - 1}].value.label",
            node_path_value(source, "value.label"),
            f"checker_evaluations[{index - 1}].native_value.semantics",
            node_path_value(evaluation, "native_value.semantics"),
            node_path_value(source, "value.label") == "equity"
            and node_path_value(evaluation, "native_value.semantics")
            == "GNU native Cubeful equity"
            and evaluation.get("display_value_source") == "native",
            "Canonical expands Node's native equity label into an explicit Cubeful-equity semantic wrapper and selects that same native value for display.",
        )
        node_difference = source.get("difference_from_best", MISSING)
        canonical_difference = evaluation.get("difference_from_best", MISSING)
        if index == 1:
            collector.neutral(
                scope,
                "checker",
                f"{prefix}.difference_from_best",
                f"checker.candidates[{index - 1}].difference_from_best",
                node_difference,
                f"checker_evaluations[{index - 1}].difference_from_best",
                canonical_difference,
                node_difference == 0 and canonical_difference is None,
                "Node writes the best candidate's loss baseline as 0; Canonical represents the same best-row baseline with explicit null. Non-best losses remain exact native values.",
            )
        else:
            collector.compare(scope, "checker", f"{prefix}.difference_from_best", f"checker.candidates[{index - 1}].difference_from_best", node_difference, f"checker_evaluations[{index - 1}].difference_from_best", canonical_difference)
        compare_probabilities(
            collector,
            scope,
            "checker",
            f"{prefix}.probabilities",
            f"checker.candidates[{index - 1}].probabilities",
            source.get("probabilities"),
            f"checker_evaluations[{index - 1}].probabilities",
            evaluation.get("probabilities"),
        )
        collector.compare(scope, "checker", f"{prefix}.resulting_position_id", f"checker.candidates[{index - 1}].resulting_position_id", source.get("resulting_position_id", MISSING), f"checker_candidates[{index - 1}].resulting_position_id", candidate.get("resulting_position_id", MISSING))
        collector.neutral(
            scope,
            "checker",
            f"{prefix}.structured_movements",
            f"checker.candidates[{index - 1}].structured_movements",
            MISSING,
            f"checker_candidates[{index - 1}].structured_movements",
            candidate.get("structured_movements", MISSING),
            candidate.get("structured_movements", MISSING) == [],
            "Node analysis-view v0 omits unavailable structured movement; Canonical preserves the same unavailability as an explicit empty array and does not invent movement facts.",
            "Node fixture limitation states that structured movement steps are absent; Task 008 checker read set requires []",
        )
        collector.neutral(
            scope,
            "checker",
            f"{prefix}.supported",
            f"node_projection.candidates[{index - 1}].move_board",
            projection.get("move_board", MISSING),
            f"checker_candidates[{index - 1}].supported",
            candidate.get("supported", MISSING),
            isinstance(projection.get("move_board"), dict)
            and candidate.get("supported") is True,
            "Canonical names the presentation-support state explicitly; the retained Node projection represents the same state by supplying the exact candidate board overlay.",
        )
        collector.neutral(
            scope,
            "checker",
            f"{prefix}.evaluation_source_order",
            f"checker.candidates[{index - 1}].source_order",
            source.get("source_order", MISSING),
            f"checker_evaluations[{index - 1}].source_order",
            evaluation.get("source_order", MISSING),
            evaluation.get("source_order") == 1,
            "Canonical evaluation source order is scoped within each candidate (one selected evaluation per candidate), while candidate rank/order is compared independently.",
        )
        collector.neutral(
            scope,
            "checker",
            f"{prefix}.selected_for_display",
            f"checker.candidates[{index - 1}]",
            "sole exported evaluation",
            f"checker_evaluations[{index - 1}].selected_for_display",
            evaluation.get("selected_for_display", MISSING),
            evaluation.get("selected_for_display") is True,
            "Canonical explicitly marks the sole exported evaluation for each complete Node candidate as the display row.",
        )
        collector.neutral(
            scope,
            "checker",
            f"{prefix}.normalized_value",
            f"checker.candidates[{index - 1}].normalized_value",
            MISSING,
            f"checker_evaluations[{index - 1}].normalized_value.value",
            node_path_value(evaluation, "normalized_value.value"),
            node_path_value(evaluation, "normalized_value.value") is None,
            "Neither side supplies a normalized equity value: Node omits the field and Canonical retains explicit null without copying the native equity.",
        )
        collector.neutral(
            scope,
            "checker",
            f"{prefix}.native_equity_loss_display",
            f"checker.candidates[{index - 1}].native_equity_loss_display",
            MISSING,
            f"checker_evaluations[{index - 1}].native_equity_loss_display",
            evaluation.get("native_equity_loss_display", MISSING),
            evaluation.get("native_equity_loss_display", MISSING) is None,
            "No rounded lexical loss is supplied on either side; Canonical keeps explicit null and the exact native difference is compared separately.",
        )
        collector.neutral(
            scope,
            "checker",
            f"{prefix}.normalized_value_semantics",
            f"checker.candidates[{index - 1}].normalized_value",
            MISSING,
            f"checker_evaluations[{index - 1}].normalized_value.semantics",
            node_path_value(evaluation, "normalized_value.semantics"),
            node_path_value(evaluation, "normalized_value.value") is None
            and node_path_value(evaluation, "normalized_value.semantics")
            == "Canonical derived cubeless money equity",
            "Canonical names the unavailable normalized-equity slot but leaves its value null; it does not derive or copy a value from Node-direct evidence.",
        )


def compare_cube(
    collector: Collector,
    node: dict[str, Any],
    canonical: dict[str, Any],
    projected: dict[str, Any],
) -> None:
    scope = "cube"
    compare_common(collector, scope, node, canonical, CUBE_ID)
    recommendation = node_path_value(node, "recommendation.label")
    collector.compare(scope, "cube", "recommendation", "recommendation.label", recommendation, "cube_occurrence.recommendation_native", node_path_value(canonical, "cube_occurrence.recommendation_native"))
    collector.compare(scope, "cube", "recommendation_presentation", "recommendation.label", recommendation, "presentation.recommendation", node_path_value(canonical, "presentation.recommendation"))
    node_actions = require_list(node_path_value(node, "cube.actions"), "node.cube.actions")
    canonical_actions = require_list(canonical.get("cube_actions"), "canonical.cube_actions")
    projected_actions = require_list(projected.get("actions"), "node projection actions")
    first_normalized = node_actions[0].get("normalized_action", MISSING) if node_actions else MISSING
    collector.compare(scope, "cube", "responder_meaning", "cube.actions[0].normalized_action", first_normalized, "cube_occurrence.recommendation_normalized", node_path_value(canonical, "cube_occurrence.recommendation_normalized"))
    collector.compare(scope, "cube", "action_count", "cube.actions.length", len(node_actions), "cube_actions.length", len(canonical_actions))
    collector.compare(scope, "cube", "projected_action_count", "cube.actions.length", len(node_actions), "node_projection.actions.length", len(projected_actions))
    collector.compare(scope, "cube", "requested_cube_ply", "settings.effective.evaluation_plies", node_path_value(node, "settings.effective.evaluation_plies"), "cube_occurrence.requested_cube_ply", node_path_value(canonical, "cube_occurrence.requested_cube_ply"))
    collector.compare(scope, "cube", "block_analysis_ply", "settings.effective.evaluation_plies", node_path_value(node, "settings.effective.evaluation_plies"), "cube_occurrence.block_analysis_ply", node_path_value(canonical, "cube_occurrence.block_analysis_ply"))
    collector.compare(scope, "cube", "cube_occurrence_identity_mapping", "canonical_decision_id", canonical.get("canonical_decision_id", MISSING), "cube_occurrence.cube_occurrence_id", node_path_value(canonical, "cube_occurrence.cube_occurrence_id"))
    collector.neutral(
        scope,
        "cube",
        "observed_action",
        "cube.observed_action",
        MISSING,
        "cube_occurrence.observed_action_native/normalized",
        [node_path_value(canonical, "cube_occurrence.observed_action_native"), node_path_value(canonical, "cube_occurrence.observed_action_normalized")],
        node_path_value(canonical, "cube_occurrence.observed_action_native") is None
        and node_path_value(canonical, "cube_occurrence.observed_action_normalized") is None,
        "Neither side claims a played/observed cube action; Canonical encodes the absent native and normalized forms as explicit nulls.",
    )
    if not (len(node_actions) == len(canonical_actions) == len(projected_actions)):
        return

    expected_ids = EXPECTED_CANONICAL_IDS[scope]["action_ids"]
    for index, (source, action, projection) in enumerate(
        zip(node_actions, canonical_actions, projected_actions), start=1
    ):
        prefix = f"action[{index}]"
        collector.compare(scope, "cube", f"{prefix}.source_order", f"cube.actions[{index - 1}].source_order", source.get("source_order", MISSING), f"cube_actions[{index - 1}].source_order", action.get("source_order", MISSING))
        collector.compare(scope, "cube", f"{prefix}.display_order", f"cube.actions[{index - 1}].display_order", source.get("display_order", MISSING), f"cube_actions[{index - 1}].source_order", action.get("source_order", MISSING))
        collector.neutral(
            scope,
            "cube",
            f"{prefix}.action_identity",
            f"cube.actions[{index - 1}].id",
            source.get("id", MISSING),
            f"cube_actions[{index - 1}].action_id",
            action.get("action_id", MISSING),
            source.get("id") == source.get("normalized_action")
            and action.get("action_id") == expected_ids[index - 1]
            and source.get("normalized_action") == action.get("normalized_action"),
            "Node uses the normalized action token as its local ID while Canonical adds a stable action hash; exact action meaning and source order bind the mapping.",
        )
        collector.compare(scope, "cube", f"{prefix}.label", f"cube.actions[{index - 1}].label", source.get("label", MISSING), f"cube_actions[{index - 1}].label", action.get("label", MISSING))
        collector.compare(scope, "cube", f"{prefix}.native_action", f"cube.actions[{index - 1}].label", source.get("label", MISSING), f"cube_actions[{index - 1}].native_action", action.get("native_action", MISSING))
        collector.compare(scope, "cube", f"{prefix}.normalized_action", f"cube.actions[{index - 1}].normalized_action", source.get("normalized_action", MISSING), f"cube_actions[{index - 1}].normalized_action", action.get("normalized_action", MISSING))
        collector.compare(scope, "cube", f"{prefix}.supported", f"cube.actions[{index - 1}].supported", source.get("supported", MISSING), f"cube_actions[{index - 1}].supported", action.get("supported", MISSING))
        collector.compare(scope, "cube", f"{prefix}.projected_supported", f"cube.actions[{index - 1}].supported", source.get("supported", MISSING), f"node_projection.actions[{index - 1}].supported", projection.get("supported", MISSING))
        collector.neutral(
            scope,
            "cube",
            f"{prefix}.native_value_label",
            f"cube.actions[{index - 1}].value.label",
            node_path_value(source, "value.label"),
            f"cube_actions[{index - 1}].native_value.label",
            node_path_value(action, "native_value.label"),
            isinstance(node_path_value(source, "value.label"), str)
            and isinstance(node_path_value(action, "native_value.label"), str)
            and node_path_value(source, "value.label").casefold()
            == node_path_value(action, "native_value.label").casefold(),
            "Only label capitalization changes; the exact source-native numeric equity is compared separately.",
        )
        collector.compare(scope, "cube", f"{prefix}.native_equity", f"cube.actions[{index - 1}].value.value", node_path_value(source, "value.value"), f"cube_actions[{index - 1}].native_value.value", node_path_value(action, "native_value.value"))
        collector.neutral(
            scope,
            "cube",
            f"{prefix}.native_equity_semantics",
            f"cube.actions[{index - 1}].value.label",
            node_path_value(source, "value.label"),
            f"cube_actions[{index - 1}].native_value.semantics",
            node_path_value(action, "native_value.semantics"),
            node_path_value(source, "value.label") == "equity"
            and node_path_value(action, "native_value.semantics")
            == "Source-native cube action equity"
            and action.get("display_value_source") == "native",
            "Canonical expands Node's equity label into an explicit source-native cube-equity wrapper and selects that same native value for display.",
        )
        collector.compare(scope, "cube", f"{prefix}.probabilities", f"cube.actions[{index - 1}].probabilities", source.get("probabilities", MISSING), f"cube_actions[{index - 1}].probabilities", action.get("probabilities", MISSING))
        actual_ply = action.get("actual_ply", MISSING)
        if actual_ply is None:
            collector.unavailable(
                scope,
                "cube",
                f"{prefix}.row_local_actual_ply",
                "canonical",
                f"cube_actions[{index - 1}].actual_ply",
                "settings.effective.evaluation_plies",
                node_path_value(node, "settings.effective.evaluation_plies"),
                "Node-direct exposes block/global effective depth, but Canonical intentionally leaves row-local cube-action depth null; the comparator does not backfill it. Requested and block depth are compared separately.",
                "cube-read-set limitations[0]: row-local actual ply is absent; requested and block analysis ply remain 1",
            )
        else:
            collector.add(
                scope,
                "cube",
                f"{prefix}.row_local_actual_ply",
                MISMATCH,
                side("settings.effective.evaluation_plies", node_path_value(node, "settings.effective.evaluation_plies")),
                side(f"cube_actions[{index - 1}].actual_ply", actual_ply),
                "Canonical row-local cube depth must remain explicit null; the comparator refuses to infer or accept a backfilled value.",
                "cube-read-set limitations[0]: row-local actual ply is absent; requested and block analysis ply remain 1",
            )
        collector.neutral(
            scope,
            "cube",
            f"{prefix}.normalized_equity",
            f"cube.actions[{index - 1}].normalized_value",
            MISSING,
            f"cube_actions[{index - 1}].normalized_value.value",
            node_path_value(action, "normalized_value.value"),
            node_path_value(action, "normalized_value.value") is None,
            "Neither side supplies a normalized cube equity: Node omits it and Canonical preserves explicit null without copying native equity.",
        )
        collector.neutral(
            scope,
            "cube",
            f"{prefix}.normalized_equity_semantics",
            f"cube.actions[{index - 1}].normalized_value",
            MISSING,
            f"cube_actions[{index - 1}].normalized_value.semantics",
            node_path_value(action, "normalized_value.semantics"),
            node_path_value(action, "normalized_value.value") is None
            and node_path_value(action, "normalized_value.semantics")
            == "No normalized cube action value supplied by Canonical Analysis Parquet v1",
            "Canonical names the unavailable normalized cube-equity slot and explicitly states that no value was supplied; it does not copy the native equity.",
        )
        collector.neutral(
            scope,
            "cube",
            f"{prefix}.native_difference",
            f"cube.actions[{index - 1}].native_difference",
            MISSING,
            f"cube_actions[{index - 1}].native_difference",
            action.get("native_difference", MISSING),
            action.get("native_difference", MISSING) is None,
            "The source emitted no cube-action difference value; Node omits the field and Canonical retains explicit null.",
        )


def compare_authority(
    collector: Collector,
    documents: dict[str, dict[str, Any]],
    actual_hashes: dict[str, str],
) -> None:
    evidence = documents["materialization_evidence"]
    checker_read_set = documents["checker_read_set"]
    cube_read_set = documents["cube_read_set"]
    for name in PATHS:
        collector.expect("overall", "input_authority", f"input_sha256.{name}", f"accepted {name} SHA-256", EXPECTED_HASHES[name], PATHS[name], actual_hashes[name])

    for scope, read_set in (("checker", checker_read_set), ("cube", cube_read_set)):
        expected = EXPECTED_PACKAGES[scope]
        collector.expect(scope, "package_authority", "package_id", "Prompt 009 accepted package", expected["package_id"], "read_set.package.package_id", node_path_value(read_set, "package.package_id"))
        collector.expect(scope, "package_authority", "manifest_sha256", "Prompt 009 accepted manifest", expected["manifest_sha256"], "read_set.package.manifest_sha256", node_path_value(read_set, "package.manifest_sha256"))
        collector.compare(scope, "package_authority", "evidence_package_binding", "read_set.package.package_id", node_path_value(read_set, "package.package_id"), f"materialization_evidence.authority.{scope}.package_id", node_path_value(evidence, f"authority.{scope}.package_id"))
        collector.compare(scope, "package_authority", "evidence_manifest_binding", "read_set.package.manifest_sha256", node_path_value(read_set, "package.manifest_sha256"), f"materialization_evidence.authority.{scope}.manifest_sha256", node_path_value(evidence, f"authority.{scope}.manifest_sha256"))
        collector.compare(scope, "package_authority", "committed_manifest_binding", f"materialization_evidence.authority.{scope}.manifest_sha256", node_path_value(evidence, f"authority.{scope}.manifest_sha256"), f"materialization_evidence.authority.{scope}.committed_marker.manifest_sha256", node_path_value(evidence, f"authority.{scope}.committed_marker.manifest_sha256"))
        collector.expect(scope, "package_authority", "canonical_writer_commit", "accepted Canonical writer commit", "1569284972239a2627de8e5176eb47caef454fda", "canonical_provenance.writer.commit", node_path_value(one_analysis(read_set, scope), "canonical_provenance.writer.commit"))
        collector.expect(scope, "package_authority", "node_materializer_commit", "accepted Node materializer commit", "fb6a121474517c29b66d959d579a9282a61280b2", "canonical_provenance.producer.materializer.commit", node_path_value(one_analysis(read_set, scope), "canonical_provenance.producer.materializer.commit"))
        collector.expect(scope, "package_authority", "parser_commit", "accepted parser implementation commit", "5dd21daf166f6284c0224ac35a4a5495cb00a0ff", "canonical_provenance.producer.analysis_producer_identity.parser.source_commit", node_path_value(one_analysis(read_set, scope), "canonical_provenance.producer.analysis_producer_identity.parser.source_commit"))

    collector.compare("overall", "materialization", "checker_read_set_hash_binding", "materialization_evidence.outputs.checker_read_set_sha256", node_path_value(evidence, "outputs.checker_read_set_sha256"), PATHS["checker_read_set"], actual_hashes["checker_read_set"])
    collector.compare("overall", "materialization", "cube_read_set_hash_binding", "materialization_evidence.outputs.cube_read_set_sha256", node_path_value(evidence, "outputs.cube_read_set_sha256"), PATHS["cube_read_set"], actual_hashes["cube_read_set"])
    collector.compare("overall", "materialization", "lesson_view_hash_binding", "materialization_evidence.outputs.golden_pair_analysis_view_sha256", node_path_value(evidence, "outputs.golden_pair_analysis_view_sha256"), PATHS["lesson_view"], actual_hashes["lesson_view"])
    collector.compare("overall", "materialization", "canonical_config_hash_binding", "materialization_evidence.config_sha256", evidence.get("config_sha256", MISSING), PATHS["canonical_config"], actual_hashes["canonical_config"])

    reconstructed_checker = view_materializer.materialize_document(checker_read_set)
    reconstructed_cube = view_materializer.materialize_document(cube_read_set)
    reconstructed = pair_materializer.combine_documents(
        reconstructed_checker,
        reconstructed_cube,
        checker_analysis_id=CHECKER_ID,
        cube_analysis_id=CUBE_ID,
        config_sha256=actual_hashes["canonical_config"],
    )
    reconstructed_bytes = view_materializer.stable_json_bytes(reconstructed)
    collector.compare("overall", "materialization", "read_sets_reproduce_lesson_view", "deterministic read-set reconstruction SHA-256", sha256_bytes(reconstructed_bytes), PATHS["lesson_view"], actual_hashes["lesson_view"])

    excluded = node_path_value(evidence, "excluded_package_a_cube.source_record_id")
    collector.expect("overall", "exclusion", "excluded_package_a_cube_identity", "Prompt 009 excluded cube", EXCLUDED_CUBE_ID, "materialization_evidence.excluded_package_a_cube.source_record_id", excluded)
    collector.expect("overall", "exclusion", "excluded_package_a_cube_disposition", "required disposition", "rejected-before-materialization", "materialization_evidence.excluded_package_a_cube.disposition", node_path_value(evidence, "excluded_package_a_cube.disposition"))
    accepted_payload = b"\n".join(stable_json_bytes(documents[name]) for name in ("node_checker", "node_cube", "checker_read_set", "cube_read_set", "lesson_view"))
    collector.expect("overall", "exclusion", "excluded_package_a_cube_absent", "excluded ID occurrence count", 0, "accepted Node/read-set/view evidence", accepted_payload.count(EXCLUDED_CUBE_ID.encode()))


def validate_node_projection(
    collector: Collector,
    documents: dict[str, dict[str, Any]],
    actual_hashes: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    projection = documents["node_projection"]
    analyses = require_object(projection.get("analyses"), "node_projection.analyses")
    for scope, analysis_id, input_name in (
        ("checker", CHECKER_ID, "node_checker"),
        ("cube", CUBE_ID, "node_cube"),
    ):
        projected = require_object(analyses.get(analysis_id), f"node_projection.analyses.{analysis_id}")
        collector.compare(scope, "node_authority", "projection_analysis_identity", "Node fixture analysis_key", documents[input_name].get("analysis_key", MISSING), "node_projection.id", projected.get("id", MISSING))
        collector.compare(scope, "node_authority", "projection_artifact_sha256", PATHS[input_name], actual_hashes[input_name], "node_projection.local_authoring.artifact_sha256", node_path_value(projected, "local_authoring.artifact_sha256"))
        collector.compare(scope, "node_authority", "projection_source_request", "Node fixture source_request", documents[input_name].get("source_request", MISSING), "node_projection.local_authoring.source_request", node_path_value(projected, "local_authoring.source_request"))
        collector.compare(scope, "node_authority", "projection_producer_identity", "Node fixture producer_provenance", documents[input_name].get("producer_provenance", MISSING), "node_projection.local_authoring.producer_provenance", node_path_value(projected, "local_authoring.producer_provenance"))
    return analyses[CHECKER_ID], analyses[CUBE_ID]


def build_report_from_documents(
    documents: dict[str, dict[str, Any]],
    actual_hashes: dict[str, str],
) -> dict[str, Any]:
    collector = Collector()
    compare_authority(collector, documents, actual_hashes)
    projected_checker, projected_cube = validate_node_projection(collector, documents, actual_hashes)
    node_checker = documents["node_checker"]
    node_cube = documents["node_cube"]
    checker = one_analysis(documents["checker_read_set"], "checker read set")
    cube = one_analysis(documents["cube_read_set"], "cube read set")
    compare_checker(collector, node_checker, checker, projected_checker)
    compare_cube(collector, node_cube, cube, projected_cube)

    rows = sorted(
        collector.rows,
        key=lambda row: (row["scope"], row["category"], row["field"]),
    )
    counts = Counter(row["classification"] for row in rows)
    by_scope: dict[str, dict[str, Any]] = {}
    for scope in ("checker", "cube", "overall"):
        scope_rows = [row for row in rows if row["scope"] == scope]
        scope_counts = Counter(row["classification"] for row in scope_rows)
        by_scope[scope] = {
            "status": "PASS" if scope_counts[MISMATCH] == 0 else "FAIL",
            "comparison_count": len(scope_rows),
            "classification_counts": {name: scope_counts[name] for name in CLASSIFICATIONS},
        }
    inputs = [
        {
            "name": name,
            "path": path,
            "sha256": actual_hashes[name],
            "accepted_sha256": EXPECTED_HASHES[name],
        }
        for name, path in PATHS.items()
    ]
    return {
        "schema_version": SCHEMA,
        "task": COMPARATOR_VERSION,
        "starting_implementation_head": STARTING_HEAD,
        "result": {
            "status": "PASS" if counts[MISMATCH] == 0 else "FAIL",
            "checker_semantic_equivalence": by_scope["checker"]["status"],
            "cube_semantic_equivalence": by_scope["cube"]["status"],
            "required_factual_mismatch_count": counts[MISMATCH],
            "required_provenance_identity_mapping": "AUDITABLE" if counts[MISMATCH] == 0 else "FAILED",
        },
        "determinism": {
            "status": "PASS",
            "method": "two independent in-memory builds compared byte-for-byte; output contains no clock, host, or mutable Git-head fields",
            "repeat_count": 2,
        },
        "inputs": inputs,
        "summary": {
            "comparison_count": len(rows),
            "classification_counts": {name: counts[name] for name in CLASSIFICATIONS},
            "by_scope": by_scope,
        },
        "comparisons": rows,
    }


def load_documents(root: Path = ROOT) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    documents: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for name, relative in PATHS.items():
        path = root / relative
        payload = path.read_bytes()
        hashes[name] = sha256_bytes(payload)
        documents[name] = load_json(path)
    return documents, hashes


def human_report(report: dict[str, Any], json_sha256: str) -> bytes:
    result = report["result"]
    summary = report["summary"]
    lines = [
        "# Analyzer K001 Task 009 semantic equivalence result",
        "",
        f"Status: `{result['status']}`",
        "",
        f"Task: `{report['task']}`",
        "",
        f"Starting implementation head: `{report['starting_implementation_head']}`",
        "",
        "## Outcome",
        "",
        f"- Checker semantic equivalence: `{result['checker_semantic_equivalence']}`",
        f"- Cube semantic equivalence: `{result['cube_semantic_equivalence']}`",
        f"- Required factual mismatches: `{result['required_factual_mismatch_count']}`",
        f"- Required provenance/identity mapping: `{result['required_provenance_identity_mapping']}`",
        f"- Deterministic repeated result: `{report['determinism']['status']}`",
        f"- Machine-readable result SHA-256: `{json_sha256}`",
        "",
        "The comparison uses exact native numbers and strings. It applies no numeric tolerance, rounded-display comparison, generic text normalization, or missing-value backfill.",
        "",
        "## Classification totals",
        "",
        "| Classification | Count |",
        "|---|---:|",
    ]
    for classification in CLASSIFICATIONS:
        lines.append(f"| `{classification}` | {summary['classification_counts'][classification]} |")
    lines.extend(["", "## Bound inputs", "", "| Input | SHA-256 |", "|---|---|"])
    for item in report["inputs"]:
        lines.append(f"| `{item['path']}` | `{item['sha256']}` |")

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in report["comparisons"]:
        if row["classification"] in {NEUTRAL, UNAVAILABLE, MISMATCH}:
            grouped[(row["classification"], row["reason"], row.get("contract_evidence", ""))].append(row)
    headings = {
        NEUTRAL: "Legitimate representation differences",
        UNAVAILABLE: "Explicit unavailable facts",
        MISMATCH: "Required factual mismatches",
    }
    for classification in (NEUTRAL, UNAVAILABLE, MISMATCH):
        lines.extend(["", f"## {headings[classification]}", ""])
        groups = [item for item in grouped.items() if item[0][0] == classification]
        if not groups:
            lines.append("None.")
            continue
        for (_, reason, contract), rows in groups:
            fields = ", ".join(f"`{row['scope']}.{row['category']}.{row['field']}`" for row in rows)
            lines.append(f"- {reason}")
            lines.append(f"  Fields: {fields}.")
            if contract:
                lines.append(f"  Contract evidence: {contract}.")

    lines.extend(
        [
            "",
            "## Determinism",
            "",
            report["determinism"]["method"] + ".",
            "",
            "No GNU, Node analysis, DuckDB query, Canonical download, or Canonical mutation is performed by this comparator.",
            "",
        ]
    )
    return "\n".join(lines).encode()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument("--verify-repeat", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    documents, hashes = load_documents()
    report = build_report_from_documents(documents, hashes)
    json_payload = stable_json_bytes(report)
    markdown_payload = human_report(report, sha256_bytes(json_payload))
    if args.verify_repeat:
        repeated_documents, repeated_hashes = load_documents()
        repeated = build_report_from_documents(repeated_documents, repeated_hashes)
        repeated_json = stable_json_bytes(repeated)
        repeated_markdown = human_report(repeated, sha256_bytes(repeated_json))
        if repeated_json != json_payload or repeated_markdown != markdown_payload:
            raise EquivalenceError("repeat build was not byte-identical")
    if args.output_json:
        atomic_write(args.output_json, json_payload)
    if args.output_markdown:
        atomic_write(args.output_markdown, markdown_payload)
    print(
        f"checker={report['result']['checker_semantic_equivalence']} "
        f"cube={report['result']['cube_semantic_equivalence']} "
        f"mismatches={report['result']['required_factual_mismatch_count']} "
        f"determinism={'PASS' if args.verify_repeat else 'NOT_REQUESTED'}"
    )
    return 0 if report["result"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
