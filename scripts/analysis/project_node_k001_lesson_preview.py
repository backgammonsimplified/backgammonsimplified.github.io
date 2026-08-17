#!/usr/bin/env python3
"""Project exact Node K001 analysis-view JSON into the shared Results Viewer."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SCHEMA = "bs-analysis-results-viewer-fixture-v1"
NODE_ANALYSIS_SCHEMA_V0 = "b" + "ms-node-analysis-view-v0"
EXPECTED_CHECKER_KEY = "sha256-52e8ef0da2e4090a81f0ab726370811812c20f76f31730c5e6d132e63b774f3d"
EXPECTED_CHECKER_GNUID = "4PPgASTgc/ABMA:cAnqAAAAAAAE"
EXPECTED_CUBE_KEY = "sha256-1217f65d4a2c203e2370edb860ffaba81090a42f69d2a5fb56f5cceb64389e01"
EXPECTED_CUBE_GNUID = "PAAAICMAAAAAAA:MAEAAAAAAAAE"
CHECKER_ASSET_ROOT = "/assets/positions/node-k001/checker/"
CUBE_ASSET_ROOT = "/assets/positions/node-k001/cube/"
SIMPLE_TOKEN = re.compile(r"^(?:[1-9]|1[0-9]|2[0-4])/(?:[1-9]|1[0-9]|2[0-4])$")


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def map_probabilities(source: dict | None) -> dict | None:
    if source is None:
        return None
    return {
        "win": source.get("win"),
        "win_gammon_or_better": source.get("win_gammon"),
        "win_backgammon": source.get("win_backgammon"),
        "lose": source.get("lose"),
        "lose_gammon_or_worse": source.get("lose_gammon"),
        "lose_backgammon": source.get("lose_backgammon"),
    }


def simple_overlay_supported(notation: str | None) -> bool:
    if not isinstance(notation, str) or not notation.strip():
        return False
    return all(SIMPLE_TOKEN.fullmatch(token) for token in notation.split())


def validate_view(view: dict, *, kind: str, key: str, gnuid: str) -> None:
    if view.get("schema_version") != NODE_ANALYSIS_SCHEMA_V0:
        raise ValueError(f"{kind} input is not a Node analysis-view v0 document")
    if view.get("analysis_kind") != kind:
        raise ValueError(f"Expected {kind} analysis-view")
    if view.get("analysis_key") != key:
        raise ValueError(f"Unexpected {kind} analysis key")
    position = view.get("source_request", {}).get("position", {})
    if position.get("format") != "gnuid" or position.get("id") != gnuid:
        raise ValueError(f"Unexpected {kind} GNUID")


def settings_text(view: dict) -> tuple[str, str]:
    requested = view.get("settings", {}).get("requested", {})
    effective = view.get("settings", {}).get("effective", {})
    requested_text = ", ".join(
        str(value)
        for value in (
            requested.get("analysis_setting"),
            requested.get("decision_type"),
            requested.get("report_mode"),
        )
        if value is not None
    )
    effective_bits = []
    for key in ("actual_evaluation_type", "evaluation_plies", "cubeful", "pruning"):
        value = effective.get(key)
        if value is not None:
            effective_bits.append(f"{key}={value}")
    return requested_text or "Not supplied", ", ".join(effective_bits) or "Not supplied"


def metadata(view: dict) -> dict:
    engine = view.get("engine", {})
    provenance = view.get("producer_provenance", {})
    parser = provenance.get("parser", {})
    requested, effective = settings_text(view)
    return {
        "engine": engine.get("name"),
        "engine_version": engine.get("version"),
        "source_family": "backgammon-node exact lesson analysis",
        "parser": parser.get("identity"),
        "provenance": (
            f"analysis {view['analysis_key']}; producer "
            f"{provenance.get('producer_identity_sha256', 'not supplied')}"
        ),
        "analysis_settings": {"requested": requested, "effective": effective},
    }


def checker_model(view: dict) -> dict:
    candidates = []
    source = sorted(
        view.get("checker", {}).get("candidates", []),
        key=lambda item: (item.get("display_order") or 10_000, item.get("source_order") or 10_000),
    )
    for candidate in source:
        rank = candidate.get("display_order")
        notation = candidate.get("notation")
        overlay = simple_overlay_supported(notation)
        evaluation = candidate.get("evaluation") or {}
        candidate_id = candidate.get("id") or f"checker-{rank}"
        candidates.append(
            {
                "id": candidate_id,
                "source_order": candidate.get("source_order"),
                "display_rank": rank,
                "move": notation,
                "evaluation": evaluation.get("type"),
                "actual_ply": evaluation.get("ply"),
                "value": candidate.get("value"),
                "difference_from_best": candidate.get("difference_from_best"),
                "probabilities": map_probabilities(candidate.get("probabilities")),
                "move_board": (
                    {
                        "image": f"{CHECKER_ASSET_ROOT}candidate-{rank}.svg",
                        "alt": f"Exact Node checker position with movement overlay for rank {rank}: {notation}.",
                    }
                    if overlay
                    else None
                ),
                "resulting_position_id": candidate.get("resulting_position_id"),
                "details": (
                    "Movement overlay is build-time rendered from this exact starting GNUID."
                    if overlay
                    else "This source notation is preserved, but no overlay is invented for unsupported notation."
                ),
            }
        )

    recommendation = view.get("recommendation", {})
    model_metadata = metadata(view)
    model_metadata["recommendation"] = recommendation.get("notation")
    model_metadata["played_move"] = view.get("played_move")
    dice = view.get("source_request", {}).get("dice")
    return {
        "id": view["analysis_key"],
        "analysis_kind": "checker",
        "title": "Exact Node checker lesson analysis",
        "subtitle": "Accepted 1-ply GNU checker record with all exported candidates",
        "fixture": True,
        "original_board": {
            "image": CHECKER_ASSET_ROOT + "starting.svg",
            "alt": "Exact Node checker lesson starting position.",
        },
        "context": {
            "score": None,
            "cube": None,
            "dice": "-".join(str(value) for value in dice) if isinstance(dice, list) else None,
            "decision": "Checker play",
        },
        "metadata": model_metadata,
        "probabilities": map_probabilities(view.get("probabilities")),
        "candidates": candidates,
        "warnings": list(view.get("warnings") or []),
        "limitations": list(view.get("limitations") or []),
    }


def cube_model(view: dict) -> dict:
    actions = []
    for action in sorted(
        view.get("cube", {}).get("actions", []),
        key=lambda item: (item.get("display_order") or 10_000, item.get("source_order") or 10_000),
    ):
        actions.append(
            {
                "id": action.get("id"),
                "label": action.get("label"),
                "normalized_action": action.get("normalized_action") or action.get("id"),
                "supported": action.get("supported", True),
                "value": action.get("value"),
                "probabilities": map_probabilities(action.get("probabilities")),
                "details": "Exact Node cube action from the accepted completed record.",
            }
        )
    recommendation = view.get("recommendation", {})
    model_metadata = metadata(view)
    model_metadata["recommendation"] = recommendation.get("label")
    return {
        "id": view["analysis_key"],
        "analysis_kind": "cube",
        "title": "Exact Node cube lesson analysis",
        "subtitle": "Accepted 1-ply GNU cube record",
        "fixture": True,
        "original_board": {
            "image": CUBE_ASSET_ROOT + "starting.svg",
            "alt": "Exact Node cube lesson starting position.",
        },
        "responder_board": {
            "image": CUBE_ASSET_ROOT + "responder.svg",
            "alt": (
                "The exact same Node cube lesson position shown from the "
                "responder's perspective after Double."
            ),
        },
        "context": {"score": None, "cube": None, "dice": None, "decision": "Cube decision"},
        "metadata": model_metadata,
        "probabilities": map_probabilities(view.get("probabilities")),
        "actions": actions,
        "warnings": list(view.get("warnings") or []),
        "limitations": list(view.get("limitations") or []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checker-view", type=Path, required=True)
    parser.add_argument("--cube-view", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    checker = load_json(args.checker_view.resolve())
    cube = load_json(args.cube_view.resolve())
    validate_view(checker, kind="checker", key=EXPECTED_CHECKER_KEY, gnuid=EXPECTED_CHECKER_GNUID)
    validate_view(cube, kind="cube", key=EXPECTED_CUBE_KEY, gnuid=EXPECTED_CUBE_GNUID)

    payload = {
        "schema_version": SCHEMA,
        "fixture_status": {
            "kind": "retained-analysis",
            "label": "Exact Node lesson data",
            "message": "These are the accepted Node K001 checker and cube analysis records, projected for the development Results Viewer.",
        },
        "analyses": {
            checker["analysis_key"]: checker_model(checker),
            cube["analysis_key"]: cube_model(cube),
        },
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"PASS: wrote {output}")
    print(f"checker: {checker['analysis_key']}")
    print(f"cube: {cube['analysis_key']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
