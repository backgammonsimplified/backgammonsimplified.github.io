#!/usr/bin/env python3
"""Project retained checker analysis into the lesson component contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_SCHEMAS = {
    "position.json": "position-v1",
    "analysis.json": "checker-analysis-v1",
    "analyzer-view.json": "checker-analyzer-view-v1",
    "manifest.json": "analysis-artifact-manifest-v1",
}


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Unable to read valid JSON from {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def sha256(path: Path) -> str:
    # The source manifest was produced from LF JSON. Windows checkouts may
    # materialize the same tracked blob with CRLF, so verify canonical LF bytes.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def require_equal(label: str, *values: object) -> None:
    if not values or any(value != values[0] for value in values[1:]):
        raise ValueError(f"Cross-file mismatch for {label}: {values!r}")


def candidate_asset_name(rank: int, resulting_position_id: str) -> str:
    safe_id = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in resulting_position_id
    )
    return f"candidate-{rank}-{safe_id}.svg"


def build_projection(fixture_dir: Path) -> dict:
    documents = {
        name: load_json(fixture_dir / name) for name in EXPECTED_SCHEMAS
    }
    for name, schema in EXPECTED_SCHEMAS.items():
        if documents[name].get("schema_version") != schema:
            raise ValueError(f"Unsupported {name} schema")

    position = documents["position.json"]
    analysis = documents["analysis.json"]
    view = documents["analyzer-view.json"]
    manifest = documents["manifest.json"]

    require_equal(
        "position_id",
        position.get("position_id"),
        analysis.get("position_id"),
        view.get("position_id"),
        manifest.get("position_id"),
    )
    require_equal(
        "state_hash",
        position.get("state_hash"),
        analysis.get("state_hash"),
        view.get("state_hash"),
        manifest.get("state_hash"),
    )
    require_equal(
        "analysis_id",
        analysis.get("analysis_id"),
        view.get("analysis_id"),
        manifest.get("analysis_id"),
    )

    manifest_files = {
        item.get("path"): item for item in manifest.get("files", [])
        if isinstance(item, dict)
    }
    for name in ("position.json", "analysis.json", "analyzer-view.json"):
        expected = manifest_files.get(name, {}).get("sha256")
        if not expected or sha256(fixture_dir / name) != expected:
            raise ValueError(f"Manifest digest mismatch for {name}")

    analysis_by_rank = {
        candidate.get("rank"): candidate
        for candidate in analysis.get("candidates", [])
        if isinstance(candidate, dict)
    }
    candidates = []
    for view_candidate in view.get("candidates", [])[:3]:
        rank = view_candidate.get("rank")
        source = analysis_by_rank.get(rank)
        if source is None:
            raise ValueError(f"Analyzer candidate rank {rank!r} is absent from analysis.json")
        require_equal("candidate move", view_candidate.get("move"), source.get("move", {}).get("display"))
        require_equal("candidate equity", view_candidate.get("equity"), source.get("equity"))
        require_equal(
            "candidate difference_from_best",
            view_candidate.get("difference_from_best"),
            source.get("difference_from_best"),
        )
        require_equal(
            "candidate resulting_position_id",
            view_candidate.get("resulting_position_id"),
            source.get("resulting_position_id"),
        )
        require_equal(
            "candidate resulting_position",
            view_candidate.get("resulting_position"),
            source.get("resulting_position"),
        )
        difference = view_candidate.get("difference_from_best")
        candidates.append(
            {
                "id": f"candidate-{rank}",
                "label": view_candidate["move"],
                "move": view_candidate["move"],
                "rank": rank,
                "image": candidate_asset_name(rank, view_candidate["resulting_position_id"]),
                "image_alt": (
                    "The retained starting position with checker movement overlay "
                    f"for rank {rank}: {view_candidate['move']}."
                ),
                "resulting_position_id": view_candidate["resulting_position_id"],
                "position_id": view["position_id"],
                "state_hash": view["state_hash"],
                "analysis_id": view["analysis_id"],
                "equity": view_candidate["equity"],
                "equity_loss": 0.0 if difference is None else abs(difference),
                "winning_probabilities": source.get("probabilities", {}),
                "explanation": view.get("explanation"),
                "missing_value_state": view.get("missing_field_indicators", {}),
            }
        )

    if len(candidates) != 3:
        raise ValueError("The lesson projection requires at least three checker candidates")
    if candidates[0]["label"] != view.get("recommendation"):
        raise ValueError("The rank-1 candidate does not match the recommendation")

    fixture_id = view["position_id"]
    return {
        "schema_version": "bs-lesson-analysis-fixture-v1",
        "fixture_status": {
            "kind": "retained-analysis",
            "label": "Retained GNU analysis",
            "message": (
                "Values come from the retained GNU 4-ply review. "
                "The reviewer is configured evidence, not proven ground truth."
            ),
        },
        "asset_root": f"/assets/positions/real-analysis/{fixture_id}/",
        "checker_cases": {
            fixture_id: {
                "source_kind": "retained-analysis",
                "title": "Checker play: compare the top three GNU candidates",
                "prompt": "Which candidate would you play with 3-1?",
                "position_id": view["position_id"],
                "state_hash": view["state_hash"],
                "analysis_id": view["analysis_id"],
                "initial": {
                    "image": "starting.svg",
                    "alt": "The retained checker position before a candidate move is selected.",
                },
                "recommendation": view["recommendation"],
                "candidates": candidates,
                "analysis": {
                    "label": "Show retained engine analysis",
                    "engine": view.get("provenance_summary", {}).get("engine"),
                    "setting": view.get("provenance_summary", {}).get("profile_id"),
                    "explanation": view.get("explanation"),
                    "missing_value_state": view.get("missing_field_indicators", {}),
                },
                "source_contract": {
                    "analyzer_view_schema": view["schema_version"],
                    "authoritative_analysis_schema": analysis["schema_version"],
                    "manifest_schema": manifest["schema_version"],
                },
            }
        },
    }


def validate_asset_contract(projection: dict, asset_dir: Path) -> None:
    checker_cases = projection.get("checker_cases", {})
    if len(checker_cases) != 1:
        raise ValueError("The real checker projection must contain one case")
    fixture = next(iter(checker_cases.values()))
    names = [fixture.get("initial", {}).get("image")]
    names.extend(candidate.get("image") for candidate in fixture.get("candidates", []))
    for name in names:
        if not isinstance(name, str) or not name.endswith(".svg"):
            raise ValueError("The checker projection contains a malformed SVG asset name")
        path = asset_dir / name
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"Missing checker SVG asset: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asset-dir", type=Path)
    args = parser.parse_args()
    projection = build_projection(args.fixture_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(projection, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if args.asset_dir is not None:
        validate_asset_contract(projection, args.asset_dir)
    print(f"PASS: wrote {args.output}")


if __name__ == "__main__":
    main()
