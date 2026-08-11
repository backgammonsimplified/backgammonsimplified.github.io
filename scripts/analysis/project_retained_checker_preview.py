#!/usr/bin/env python3
"""Project the accepted retained checker fixture into the shared Results Viewer view model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_DIR = (
    ROOT / "fixtures" / "real-analysis" / "checker-sage-gnu-disagreement-001"
)
DEFAULT_OUTPUT = ROOT / "site" / "data" / "analyzer-retained-checker-preview.json"
ASSET_ROOT = "/assets/positions/real-analysis/checker-sage-gnu-disagreement-001/"
SCHEMA = "bs-analysis-results-viewer-fixture-v1"


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


def candidate_asset_name(rank: int, resulting_position_id: str) -> str:
    safe = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in resulting_position_id
    )
    return f"candidate-{rank}-{safe}.svg"


def build_projection(fixture_dir: Path) -> dict:
    position = load_json(fixture_dir / "position.json")
    analysis = load_json(fixture_dir / "analysis.json")
    view = load_json(fixture_dir / "analyzer-view.json")

    if position.get("schema_version") != "position-v1":
        raise ValueError("Unsupported retained position schema")
    if analysis.get("schema_version") != "checker-analysis-v1":
        raise ValueError("Unsupported retained checker analysis schema")
    if view.get("schema_version") != "checker-analyzer-view-v1":
        raise ValueError("Unsupported retained analyzer view schema")
    for key in ("position_id", "state_hash"):
        if position.get(key) != analysis.get(key) or position.get(key) != view.get(key):
            raise ValueError(f"Cross-file mismatch for {key}")
    if analysis.get("analysis_id") != view.get("analysis_id"):
        raise ValueError("Cross-file mismatch for analysis_id")

    analysis_by_rank = {
        candidate.get("rank"): candidate
        for candidate in analysis.get("candidates", [])
        if isinstance(candidate, dict)
    }
    candidates = []
    for viewed in view.get("candidates", [])[:3]:
        rank = viewed.get("rank")
        source = analysis_by_rank.get(rank)
        if source is None:
            raise ValueError(f"Missing authoritative candidate rank {rank!r}")
        if viewed.get("move") != source.get("move", {}).get("display"):
            raise ValueError(f"Move mismatch at rank {rank}")
        if viewed.get("resulting_position_id") != source.get("resulting_position_id"):
            raise ValueError(f"Resulting-position mismatch at rank {rank}")
        difference = source.get("difference_from_best")
        if difference is None and rank == 1:
            difference = 0.0
        candidates.append(
            {
                "id": f"retained-checker-candidate-{rank}",
                "source_order": rank,
                "display_rank": rank,
                "move": source.get("move", {}).get("display"),
                "evaluation": source.get("evaluation_type"),
                "actual_ply": source.get("actual_ply"),
                "value": {"label": "Equity", "value": source.get("equity")},
                "difference_from_best": difference,
                "probabilities": map_probabilities(source.get("probabilities")),
                "move_board": {
                    "image": ASSET_ROOT
                    + candidate_asset_name(rank, source["resulting_position_id"]),
                    "alt": (
                        "The retained starting position with checker movement overlay "
                        f"for rank {rank}: {source.get('move', {}).get('display')}."
                    ),
                },
                "resulting_position_id": source.get("resulting_position_id"),
                "details": (
                    f"Retained source line {source.get('source_line_number')}; "
                    "the SVG keeps the same starting position and overlays this candidate move."
                ),
            }
        )

    if len(candidates) != 3:
        raise ValueError("Retained Analyzer preview requires three checker candidates")

    state = position["state"]
    profile = analysis.get("profile", {})
    settings = profile.get("settings", {})
    top_probabilities = candidates[0]["probabilities"]
    requested = f"Requested {settings.get('requested_ply', 'Not supplied')}-ply cubeful checker review"
    effective = (
        f"{settings.get('candidate_count', 'Not supplied')} candidates; "
        f"candidate set {settings.get('candidate_set_status', 'Not supplied')}; "
        "shown candidates actual 4-ply"
    )

    return {
        "schema_version": SCHEMA,
        "fixture_status": {
            "kind": "retained-analysis",
            "label": "Retained GNU analysis",
            "message": (
                "This development preview uses accepted retained GNU 4-ply evidence. "
                "It is not yet materialized from Canonical Parquet v1."
            ),
        },
        "analyses": {
            "retained-checker-preview": {
                "id": "retained-checker-preview",
                "analysis_kind": "checker",
                "title": "Retained GNU 4-ply checker analysis",
                "subtitle": (
                    "One factual starting position with candidate movement overlays and persistent analysis bars"
                ),
                "fixture": True,
                "original_board": {
                    "image": ASSET_ROOT + "starting.svg",
                    "alt": "The retained checker position before any candidate movement overlay.",
                },
                "context": {
                    "score": (
                        f"{state['score']['player']}-{state['score']['opponent']} "
                        f"to {state['score']['match_length']}"
                    ),
                    "cube": f"{state['cube']['value']}, {state['cube']['owner']}",
                    "dice": "-".join(str(value) for value in state.get("dice", [])),
                    "decision": "Checker play",
                },
                "metadata": {
                    "engine": "GNU Backgammon",
                    "engine_version": None,
                    "source_family": "retained Sage-vs-GNU Stage 1 review",
                    "parser": analysis.get("parser_identity", {}).get("name"),
                    "provenance": (
                        f"retained position {position['position_id']}; "
                        f"analysis {analysis['analysis_id']}"
                    ),
                    "played_move": analysis.get("played_move"),
                    "recommendation": analysis.get("recommended_move", {}).get("display"),
                    "analysis_settings": {
                        "requested": requested,
                        "effective": effective,
                    },
                },
                "probabilities": top_probabilities,
                "candidates": candidates,
                "warnings": [
                    "GNU 4-ply is configured reviewer evidence, not proven ground truth.",
                    "Candidate SVGs are build-time Backgammonboard renders of the same starting position with movement overlays.",
                ],
                "limitations": [
                    *analysis.get("limitations", []),
                    "This retained preview is an interim consumer proof; Canonical Parquet v1 remains the target source.",
                    "The current retained R renderer structures this fixture's simple point-to-point notation with board_moves() and validates the applied checker arrangement against analyzer-view.json.",
                ],
            }
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    projection = build_projection(args.fixture_dir.resolve())
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(projection, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"PASS: wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
