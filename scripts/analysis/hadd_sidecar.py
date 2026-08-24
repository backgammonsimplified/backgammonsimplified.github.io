"""Validate and attach the frozen Explainer K002 HADD derived-facts sidecar.

This module is a read-only integration adapter.  It never executes HADD and it
never creates recommendation semantics.  A sidecar is either accepted in full
against exact identities and stable factual joins, or no HADD fields are
attached to the Analyzer presentation document.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any


SIDECAR_SCHEMA = "explainer-hadd-derived-facts-sidecar-v1"
CONTRACT_VERSION = "explainer-k002-compact-hadd-integration-contract-v1"
CONTRACT_DESCRIPTOR_SHA256 = "a7a0464f3f39b2fc55a798cd8eb644c502f1d7c4dde20edaa8fe4f3f5190a9ca"
SELECTED_ARCHITECTURE = "ridge-ranking-hadd-value-explanation-sidecar-v1"
EVIDENCE_PACKAGE_IDENTITY = "f40ba9417896383a94e48012843eb0f45e177430e746cd01080f8243c5751424"
MODEL = {
    "compact_evidence_identity_sha256": "1b1ac421765ae6e430a1713fc14f6eed28dfca03bd35fda98c45d1b3959cffda",
    "compact_metadata_identity_sha256": "c98357f30265afdca8848021fed72245c3d1472e64caf73ce49ca48294e7c138",
    "runtime_id": "explainer-position-value-hadd-p3-1m-compact-runtime-v1",
    "source_model_id": "explainer-position-value-p3-hierarchical-additive-logit-v1",
    "source_model_identity_sha256": "d2c59282821ef1e33aae61ceafb8675368577de3ce3012d4ad50f6b16d8496c1",
}
FEATURE_SYSTEM = {
    "feature_count": 351,
    "feature_registry_sha256": "30ede35745bbbc645683f93473ef67cd9e21ff1f152a7369c26498c350fd0287",
    "feature_set_identity": "explainer-position-value-p3-v1-30ede35745bbbc64",
    "ordered_feature_ids_sha256": "8d8c75e2fd74d9367f343b28c26f50ff89f906c308bb8f7d28efe99942b807ae",
}
TARGET = {
    "calculated_cubeful": "CUBEFUL_CALCULATION_AUTHORITY_BLOCKED",
    "position_perspective": "normalized_static_post_move_next_player_on_roll",
    "probability_derived_cubeless": "cumulative-six-probabilities-money-equity-v1",
    "probability_hierarchy": "frozen-five-conditional-soft-binomial-hierarchy-v1",
}
GENERATION = {
    "deterministic": True,
    "new_gnu_computations": 0,
    "new_labels": 0,
    "new_source_matches": 0,
    "new_training_refits": 0,
    "producer_version": "explainer-hadd-derived-facts-sidecar-producer-v1",
    "runtime_dependencies": ["Python standard library", "NumPy"],
}
AUTHORITIES = {
    "explainer_ridge_recommendation": "external_sole_recommendation_authority",
    "factual_native_engine": "external_read_only_not_redefined",
    "hadd_conditional_logit_explanation": "this_sidecar",
    "hadd_position_value_probability": "this_sidecar",
}
HEADS = ["q_win", "q_wg", "q_wbg", "q_lg", "q_lbg"]
PROBABILITY_KEYS = [
    "win",
    "win_gammon_or_better",
    "win_backgammon",
    "lose_gammon_or_worse",
    "lose_backgammon",
]
TOLERANCE = 1e-12


class HaddSidecarError(ValueError):
    """A complete HADD sidecar or its factual joins are incompatible."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise HaddSidecarError(f"duplicate_json_key:{key}")
        value[key] = item
    return value


def load_sidecar(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except HaddSidecarError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise HaddSidecarError("missing_or_malformed_sidecar") from error
    if not isinstance(value, dict):
        raise HaddSidecarError("sidecar_not_object")
    return value


def _stable_compact(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise HaddSidecarError("non_finite_or_unstable_json") from error


def _exact_keys(value: Any, expected: set[str], path: str, optional: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HaddSidecarError(f"{path}:not_object")
    allowed = expected | (optional or set())
    if set(value) != expected | (set(value) & (optional or set())) or not expected.issubset(value):
        raise HaddSidecarError(f"{path}:unexpected_or_missing_fields")
    if not set(value).issubset(allowed):
        raise HaddSidecarError(f"{path}:unexpected_or_missing_fields")
    return value


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise HaddSidecarError(f"{path}:invalid_identifier")
    return value


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise HaddSidecarError(f"{path}:non_finite_number")
    return float(value)


def _five(value: Any, path: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 5:
        raise HaddSidecarError(f"{path}:expected_five_numbers")
    return [_number(item, f"{path}[{index}]") for index, item in enumerate(value)]


def _close(left: float, right: float, path: str) -> None:
    if abs(left - right) > TOLERANCE:
        raise HaddSidecarError(f"{path}:reconstruction_mismatch")


def _contributions(value: Any, path: str) -> tuple[list[dict[str, Any]], list[str], list[float]]:
    if not isinstance(value, list) or len(value) != FEATURE_SYSTEM["feature_count"]:
        raise HaddSidecarError(f"{path}:wrong_feature_count")
    ids: list[str] = []
    sums = [0.0] * 5
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        row = _exact_keys(
            item,
            {"feature_id", "conditional_logit_contributions"},
            f"{path}[{index}]",
        )
        feature_id = _identifier(row["feature_id"], f"{path}[{index}].feature_id")
        if feature_id in ids:
            raise HaddSidecarError(f"{path}:duplicate_feature_id")
        numbers = _five(
            row["conditional_logit_contributions"],
            f"{path}[{index}].conditional_logit_contributions",
        )
        ids.append(feature_id)
        for head in range(5):
            sums[head] += numbers[head]
        rows.append(row)
    ordered_hash = hashlib.sha256(_stable_compact(ids)).hexdigest()
    if ordered_hash != FEATURE_SYSTEM["ordered_feature_ids_sha256"]:
        raise HaddSidecarError(f"{path}:wrong_feature_order")
    return rows, ids, sums


def _probabilities(value: Any, path: str) -> dict[str, float]:
    probabilities = _exact_keys(value, set(PROBABILITY_KEYS), path)
    result = {key: _number(probabilities[key], f"{path}.{key}") for key in PROBABILITY_KEYS}
    if any(number < 0 or number > 1 for number in result.values()):
        raise HaddSidecarError(f"{path}:probability_out_of_range")
    if not (
        result["win_backgammon"] <= result["win_gammon_or_better"] <= result["win"]
        and result["lose_backgammon"] <= result["lose_gammon_or_worse"] <= 1 - result["win"]
    ):
        raise HaddSidecarError(f"{path}:probability_hierarchy_invalid")
    return result


def _validate_record(value: Any, index: int) -> tuple[dict[str, Any], list[str]]:
    path = f"records[{index}]"
    required = {
        "position_id", "decision_id", "candidate_id", "candidate_concept_id",
        "result_position_id", "position_perspective", "cumulative_probabilities",
        "lose_probability", "probability_derived_cubeless", "conditional_logit_evidence",
    }
    record = _exact_keys(value, required, path, {"source_occurrence_id"})
    for key in ("position_id", "decision_id", "candidate_id", "candidate_concept_id", "result_position_id"):
        _identifier(record[key], f"{path}.{key}")
    if record["position_id"] != record["result_position_id"]:
        raise HaddSidecarError(f"{path}:result_position_invariant")
    if record["position_perspective"] != TARGET["position_perspective"]:
        raise HaddSidecarError(f"{path}:wrong_perspective")
    if "source_occurrence_id" in record:
        _identifier(record["source_occurrence_id"], f"{path}.source_occurrence_id")
    probabilities = _probabilities(record["cumulative_probabilities"], f"{path}.cumulative_probabilities")
    lose = _number(record["lose_probability"], f"{path}.lose_probability")
    _close(lose, 1 - probabilities["win"], f"{path}.lose_probability")
    expected_value = (
        2 * probabilities["win"] - 1
        + probabilities["win_gammon_or_better"] + probabilities["win_backgammon"]
        - probabilities["lose_gammon_or_worse"] - probabilities["lose_backgammon"]
    )
    _close(
        _number(record["probability_derived_cubeless"], f"{path}.probability_derived_cubeless"),
        expected_value,
        f"{path}.probability_derived_cubeless",
    )
    evidence = _exact_keys(
        record["conditional_logit_evidence"],
        {"heads", "intercepts", "conditional_logits", "feature_contributions",
         "reconstructed_conditional_logits", "maximum_absolute_reconstruction_error", "additive_scale"},
        f"{path}.conditional_logit_evidence",
    )
    if evidence["heads"] != HEADS or evidence["additive_scale"] != "conditional_logit_only":
        raise HaddSidecarError(f"{path}:wrong_logit_semantics")
    intercepts = _five(evidence["intercepts"], f"{path}.intercepts")
    logits = _five(evidence["conditional_logits"], f"{path}.conditional_logits")
    reconstructed = _five(evidence["reconstructed_conditional_logits"], f"{path}.reconstructed")
    error = _number(evidence["maximum_absolute_reconstruction_error"], f"{path}.maximum_error")
    if error < 0 or error > TOLERANCE:
        raise HaddSidecarError(f"{path}:reported_reconstruction_error")
    _, feature_ids, sums = _contributions(evidence["feature_contributions"], f"{path}.feature_contributions")
    for head in range(5):
        _close(intercepts[head] + sums[head], logits[head], f"{path}.conditional_logit[{head}]")
        _close(reconstructed[head], logits[head], f"{path}.reconstructed[{head}]")
    return record, feature_ids


def validate_sidecar(sidecar: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "package_identity_sha256", "integration_contract",
        "selected_architecture", "authorities", "model", "feature_system",
        "target", "records", "ab_explanations", "generation",
    }
    _exact_keys(sidecar, required, "sidecar")
    if sidecar["schema_version"] != SIDECAR_SCHEMA:
        raise HaddSidecarError("wrong_schema_version")
    integration = _exact_keys(sidecar["integration_contract"], {"version", "descriptor_sha256"}, "integration_contract")
    if integration != {"version": CONTRACT_VERSION, "descriptor_sha256": CONTRACT_DESCRIPTOR_SHA256}:
        raise HaddSidecarError("wrong_integration_contract")
    if sidecar["selected_architecture"] != SELECTED_ARCHITECTURE:
        raise HaddSidecarError("wrong_selected_architecture")
    if sidecar["authorities"] != AUTHORITIES:
        raise HaddSidecarError("wrong_authority_model")
    if sidecar["model"] != MODEL:
        raise HaddSidecarError("wrong_model_or_compact_runtime_identity")
    if sidecar["feature_system"] != FEATURE_SYSTEM:
        raise HaddSidecarError("wrong_feature_system_identity")
    if sidecar["target"] != TARGET:
        raise HaddSidecarError("wrong_target_or_perspective_identity")
    if sidecar["generation"] != GENERATION:
        raise HaddSidecarError("wrong_generation_or_zero_activity_identity")
    supplied_package = _identifier(sidecar["package_identity_sha256"], "package_identity_sha256")
    identity_input = {key: value for key, value in sidecar.items() if key != "package_identity_sha256"}
    if hashlib.sha256(_stable_compact(identity_input)).hexdigest() != supplied_package:
        raise HaddSidecarError("wrong_sidecar_package_identity")
    if not isinstance(sidecar["records"], list) or not sidecar["records"]:
        raise HaddSidecarError("records_missing")
    records: dict[tuple[str, str], dict[str, Any]] = {}
    record_features: list[str] | None = None
    positions: set[str] = set()
    for index, item in enumerate(sidecar["records"]):
        record, feature_ids = _validate_record(item, index)
        key = (record["decision_id"], record["candidate_id"])
        if key in records or record["position_id"] in positions:
            raise HaddSidecarError("duplicate_or_ambiguous_record_identity")
        if record_features is not None and feature_ids != record_features:
            raise HaddSidecarError("inconsistent_feature_order")
        record_features = feature_ids
        records[key] = record
        positions.add(record["position_id"])
    if not isinstance(sidecar["ab_explanations"], list):
        raise HaddSidecarError("ab_explanations_not_array")
    explanations: set[tuple[str, str, str]] = set()
    for index, value in enumerate(sidecar["ab_explanations"]):
        path = f"ab_explanations[{index}]"
        ab = _exact_keys(value, {
            "explanation_id", "decision_id", "candidate_a_id", "candidate_b_id",
            "conditional_logit_difference", "per_feature_conditional_logit_difference",
            "reconstructed_conditional_logit_difference", "probability_differences",
            "probability_derived_cubeless_difference", "maximum_absolute_reconstruction_error",
            "additive_scale", "difference_order",
        }, path)
        for key in ("explanation_id", "decision_id", "candidate_a_id", "candidate_b_id"):
            _identifier(ab[key], f"{path}.{key}")
        key = (ab["decision_id"], ab["candidate_a_id"], ab["candidate_b_id"])
        if key in explanations or ab["candidate_a_id"] == ab["candidate_b_id"]:
            raise HaddSidecarError(f"{path}:duplicate_or_ambiguous_identity")
        explanations.add(key)
        expected_explanation_id = hashlib.sha256(
            _stable_compact(
                [SIDECAR_SCHEMA, ab["decision_id"], ab["candidate_a_id"], ab["candidate_b_id"]]
            )
        ).hexdigest()
        if ab["explanation_id"] != expected_explanation_id:
            raise HaddSidecarError(f"{path}:wrong_explanation_identity")
        record_a = records.get((ab["decision_id"], ab["candidate_a_id"]))
        record_b = records.get((ab["decision_id"], ab["candidate_b_id"]))
        if record_a is None or record_b is None:
            raise HaddSidecarError(f"{path}:unknown_candidate_join")
        if ab["difference_order"] != "A-minus-B" or ab["additive_scale"] != "conditional_logit_only":
            raise HaddSidecarError(f"{path}:wrong_difference_semantics")
        differences = _five(ab["conditional_logit_difference"], f"{path}.conditional_logit_difference")
        reconstructed = _five(ab["reconstructed_conditional_logit_difference"], f"{path}.reconstructed")
        _, feature_ids, sums = _contributions(ab["per_feature_conditional_logit_difference"], f"{path}.per_feature")
        if feature_ids != record_features:
            raise HaddSidecarError(f"{path}:wrong_feature_order")
        logits_a = record_a["conditional_logit_evidence"]["conditional_logits"]
        logits_b = record_b["conditional_logit_evidence"]["conditional_logits"]
        for head in range(5):
            _close(differences[head], logits_a[head] - logits_b[head], f"{path}.difference[{head}]")
            _close(sums[head], differences[head], f"{path}.sum[{head}]")
            _close(reconstructed[head], differences[head], f"{path}.reconstructed[{head}]")
        probability_differences = _exact_keys(ab["probability_differences"], set(PROBABILITY_KEYS), f"{path}.probability_differences")
        for probability in PROBABILITY_KEYS:
            _close(
                _number(probability_differences[probability], f"{path}.probability_differences.{probability}"),
                record_a["cumulative_probabilities"][probability] - record_b["cumulative_probabilities"][probability],
                f"{path}.probability_differences.{probability}",
            )
        _close(
            _number(ab["probability_derived_cubeless_difference"], f"{path}.value_difference"),
            record_a["probability_derived_cubeless"] - record_b["probability_derived_cubeless"],
            f"{path}.value_difference",
        )
        error = _number(ab["maximum_absolute_reconstruction_error"], f"{path}.maximum_error")
        if error < 0 or error > TOLERANCE:
            raise HaddSidecarError(f"{path}:reported_reconstruction_error")
    return sidecar


def attach_sidecar(document: dict[str, Any], sidecar: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with HADD attached after complete validation and exact joins."""
    validate_sidecar(sidecar)
    output = copy.deepcopy(document)
    analyses = output.get("analyses")
    if not isinstance(analyses, dict):
        raise HaddSidecarError("factual_document_missing_analyses")
    factual: dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]] = {}
    for analysis in analyses.values():
        if not isinstance(analysis, dict) or analysis.get("analysis_kind") != "checker":
            continue
        context = analysis.get("canonical_context") or {}
        decision_id = context.get("canonical_decision_id")
        candidates = analysis.get("candidates")
        if not isinstance(decision_id, str) or not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict) or not isinstance(candidate.get("id"), str):
                continue
            key = (decision_id, candidate["id"])
            if key in factual:
                raise HaddSidecarError("duplicate_or_ambiguous_factual_candidate_identity")
            factual[key] = (analysis, candidate)
    joined: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    analyses_with_hadd: dict[str, dict[str, Any]] = {}
    for record in sidecar["records"]:
        key = (record["decision_id"], record["candidate_id"])
        match = factual.get(key)
        if match is None:
            raise HaddSidecarError("wrong_or_missing_factual_join_identity")
        analysis, candidate = match
        if (
            candidate.get("candidate_concept_id") != record["candidate_concept_id"]
            or candidate.get("resulting_position_id") != record["result_position_id"]
            or record["position_id"] != record["result_position_id"]
        ):
            raise HaddSidecarError("incompatible_candidate_concept_or_result_position_join")
        joined.append((analysis, candidate, record))
        analyses_with_hadd[record["decision_id"]] = analysis
    sidecar_keys = {(record["decision_id"], record["candidate_id"]) for record in sidecar["records"]}
    for decision_id, analysis in analyses_with_hadd.items():
        factual_keys = {
            (decision_id, candidate["id"])
            for candidate in analysis.get("candidates", [])
            if isinstance(candidate, dict) and isinstance(candidate.get("id"), str)
        }
        if factual_keys != {key for key in sidecar_keys if key[0] == decision_id}:
            raise HaddSidecarError("partial_decision_record_coverage")
    for analysis, candidate, record in joined:
        candidate["hadd_derived_facts"] = {
            "conditional_logit_evidence": record["conditional_logit_evidence"],
            "position_id": record["position_id"],
            "position_perspective": record["position_perspective"],
            "probabilities": {
                **record["cumulative_probabilities"],
                "lose": record["lose_probability"],
            },
            "probability_derived_cubeless": record["probability_derived_cubeless"],
        }
        analysis.setdefault("hadd", {
            "status": "available",
            "authority": {
                "hadd_ranking_authorized": False,
                "ridge_recommendation": "sole Explainer recommendation authority",
                "native_engine_recommendation": "factual native engine output",
                "value": "model-derived resulting-position cubeless value",
                "probabilities": "model-derived resulting-position probabilities",
                "explanation": "conditional-logit contribution evidence",
                "calculated_cubeful": "CUBEFUL_CALCULATION_AUTHORITY_BLOCKED",
            },
            "model": sidecar["model"],
            "feature_system": sidecar["feature_system"],
            "package_identity_sha256": sidecar["package_identity_sha256"],
            "selected_architecture": SELECTED_ARCHITECTURE,
            "position_perspective": sidecar["target"]["position_perspective"],
            "ab_explanations": [],
        })
    for explanation in sidecar["ab_explanations"]:
        analysis = analyses_with_hadd.get(explanation["decision_id"])
        if analysis is None:
            raise HaddSidecarError("explanation_decision_join_missing")
        analysis["hadd"]["ab_explanations"].append(explanation)
    output["hadd_integration"] = {
        "status": "available",
        "schema_version": SIDECAR_SCHEMA,
        "integration_contract_version": CONTRACT_VERSION,
        "integration_contract_descriptor_sha256": CONTRACT_DESCRIPTOR_SHA256,
        "selected_architecture": SELECTED_ARCHITECTURE,
        "immutable_evidence_package_identity_sha256": EVIDENCE_PACKAGE_IDENTITY,
        "sidecar_package_identity_sha256": sidecar["package_identity_sha256"],
    }
    return output


def unavailable(document: dict[str, Any], reason: str) -> dict[str, Any]:
    output = copy.deepcopy(document)
    output["hadd_integration"] = {
        "status": "unavailable",
        "reason": reason,
        "fabricated_content": False,
    }
    return output
