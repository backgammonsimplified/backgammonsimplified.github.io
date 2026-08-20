#!/usr/bin/env python3
"""Materialize completed local Node analyses for the shared Results Viewer.

This is a local authoring adapter, not a Canonical data authority.  It consumes
already-completed Node analysis-view v0 artifacts and never invokes an engine.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


CONFIG_SCHEMA = "bs-local-node-analysis-authoring-v1"
NODE_SCHEMA = "b" + "ms-node-analysis-view-v0"
VIEWER_SCHEMA = "bs-analysis-results-viewer-fixture-v1"
LOCAL_AUTHORITY = "local-development-only"
SUPPORTED_KINDS = {"checker", "cube"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SIMPLE_MOVE = re.compile(r"^(?:[1-9]|1[0-9]|2[0-4])/(?:[1-9]|1[0-9]|2[0-4])$")
SAFE_SUBDIR = re.compile(r"^[a-z0-9]+(?:[a-z0-9_-]*[a-z0-9])?$")


class AuthoringError(ValueError):
    """Input cannot be projected without guessing."""


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuthoringError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (OSError, json.JSONDecodeError) as error:
        raise AuthoringError(f"Unable to read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise AuthoringError(f"{path} must contain one JSON object")
    return value


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuthoringError(f"{path} must be an object")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise AuthoringError(f"{path} must be an array")
    return value


def require_keys(value: dict[str, Any], keys: tuple[str, ...], path: str) -> None:
    missing = [key for key in keys if key not in value]
    if missing:
        raise AuthoringError(f"{path} is missing required key(s): {', '.join(missing)}")


def require_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuthoringError(f"{path} must be a non-empty string")
    return value


def optional_text(value: Any, path: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise AuthoringError(f"{path} must be text or null")
    return value


def optional_number(value: Any, path: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AuthoringError(f"{path} must be a number or null")
    return value


def optional_integer(value: Any, path: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise AuthoringError(f"{path} must be an integer or null")
    return value


def resolve_path(value: Any, repo_root: Path, path: str) -> Path:
    text = require_text(value, path)
    candidate = Path(os.path.expandvars(os.path.expanduser(text)))
    return (candidate if candidate.is_absolute() else repo_root / candidate).resolve()


def stable_bytes(value: object) -> bytes:
    try:
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        # Preserve the retired Node schema value without reactivating the old
        # publication namespace in checked source text. JSON decoding is exact.
        payload = payload.replace(NODE_SCHEMA, "b\\u006ds-node-analysis-view-v0")
        return payload.encode()
    except (TypeError, ValueError) as error:
        raise AuthoringError(f"Output is not stable JSON: {error}") from error


def write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise AuthoringError(f"Unable to hash artifact {path}: {error}") from error
    return digest.hexdigest()


def map_probabilities(value: Any, path: str) -> dict[str, Any] | None:
    if value is None:
        return None
    source = require_object(value, path)
    keys = (
        "win", "win_gammon", "win_backgammon", "lose", "lose_gammon", "lose_backgammon"
    )
    require_keys(source, keys, path)
    return {
        "win": optional_number(source["win"], f"{path}.win"),
        "win_gammon_or_better": optional_number(source["win_gammon"], f"{path}.win_gammon"),
        "win_backgammon": optional_number(source["win_backgammon"], f"{path}.win_backgammon"),
        "lose": optional_number(source["lose"], f"{path}.lose"),
        "lose_gammon_or_worse": optional_number(source["lose_gammon"], f"{path}.lose_gammon"),
        "lose_backgammon": optional_number(source["lose_backgammon"], f"{path}.lose_backgammon"),
    }


def simple_overlay_supported(notation: str) -> bool:
    return bool(notation.strip()) and all(SIMPLE_MOVE.fullmatch(token) for token in notation.split())


def settings_text(view: dict[str, Any]) -> tuple[str, str]:
    settings = require_object(view.get("settings"), "artifact.settings")
    requested = require_object(settings.get("requested"), "artifact.settings.requested")
    effective = require_object(settings.get("effective"), "artifact.settings.effective")
    require_keys(
        requested,
        ("analysis_setting", "decision_type", "report_mode"),
        "artifact.settings.requested",
    )
    require_keys(
        effective,
        ("actual_evaluation_type", "evaluation_plies", "cubeful", "pruning"),
        "artifact.settings.effective",
    )
    for key in ("analysis_setting", "decision_type", "report_mode"):
        optional_text(requested[key], f"artifact.settings.requested.{key}")
    optional_text(
        effective["actual_evaluation_type"],
        "artifact.settings.effective.actual_evaluation_type",
    )
    optional_integer(
        effective["evaluation_plies"],
        "artifact.settings.effective.evaluation_plies",
    )
    for key in ("cubeful", "pruning"):
        if effective[key] is not None and not isinstance(effective[key], bool):
            raise AuthoringError(
                f"artifact.settings.effective.{key} must be boolean or null"
            )
    requested_text = ", ".join(
        str(requested[key])
        for key in ("analysis_setting", "decision_type", "report_mode")
        if requested.get(key) is not None
    )
    effective_text = ", ".join(
        f"{key}={effective[key]}"
        for key in ("actual_evaluation_type", "evaluation_plies", "cubeful", "pruning")
        if effective.get(key) is not None
    )
    return requested_text or "Not supplied", effective_text or "Not supplied"


def validate_common(view: dict[str, Any], selection: dict[str, Any], path: str) -> None:
    require_keys(
        view,
        (
            "schema_version", "analysis_kind", "analysis_key", "source_request", "engine",
            "producer_provenance", "settings", "probabilities", "recommendation", "warnings", "limitations",
        ),
        path,
    )
    if view["schema_version"] != NODE_SCHEMA:
        raise AuthoringError(f"{path}.schema_version is not Node analysis-view v0")
    kind = require_text(selection.get("kind"), f"{path}.selection.kind")
    if kind not in SUPPORTED_KINDS or view["analysis_kind"] != kind:
        raise AuthoringError(f"{path} decision kind does not match the explicit selection")
    analysis_id = require_text(selection.get("analysis_id"), f"{path}.selection.analysis_id")
    if view["analysis_key"] != analysis_id:
        raise AuthoringError(f"{path} analysis identity does not match the explicit selection")
    request = require_object(view["source_request"], f"{path}.source_request")
    require_keys(request, ("position", "dice"), f"{path}.source_request")
    position = require_object(request.get("position"), f"{path}.source_request.position")
    require_keys(position, ("format", "id"), f"{path}.source_request.position")
    if position["format"] != "gnuid":
        raise AuthoringError(f"{path}.source_request.position.format must be gnuid")
    require_text(position["id"], f"{path}.source_request.position.id")
    engine = require_object(view["engine"], f"{path}.engine")
    require_keys(engine, ("name", "version"), f"{path}.engine")
    require_text(engine["name"], f"{path}.engine.name")
    optional_text(engine["version"], f"{path}.engine.version")
    provenance = require_object(view["producer_provenance"], f"{path}.producer_provenance")
    require_keys(provenance, ("producer_identity_sha256", "parser"), f"{path}.producer_provenance")
    require_text(provenance["producer_identity_sha256"], f"{path}.producer_provenance.producer_identity_sha256")
    parser = require_object(provenance["parser"], f"{path}.producer_provenance.parser")
    require_text(parser.get("identity"), f"{path}.producer_provenance.parser.identity")
    settings_text(view)
    map_probabilities(view["probabilities"], f"{path}.probabilities")
    for key in ("warnings", "limitations"):
        for index, item in enumerate(require_list(view[key], f"{path}.{key}")):
            require_text(item, f"{path}.{key}[{index}]")


def presentation(selection: dict[str, Any], path: str) -> dict[str, Any]:
    value = require_object(selection.get("presentation"), f"{path}.presentation")
    require_keys(value, ("title", "subtitle", "decision", "original_board_alt"), f"{path}.presentation")
    for key in ("title", "subtitle", "decision", "original_board_alt"):
        require_text(value[key], f"{path}.presentation.{key}")
    return value


def common_model(
    view: dict[str, Any], selection: dict[str, Any], public_asset_root: str,
    artifact_hash: str, path: str,
) -> dict[str, Any]:
    display = presentation(selection, path)
    requested, effective = settings_text(view)
    provenance = view["producer_provenance"]
    engine = view["engine"]
    request = view["source_request"]
    kind = view["analysis_kind"]
    subdir = require_text(selection.get("asset_subdir"), f"{path}.asset_subdir")
    if not SAFE_SUBDIR.fullmatch(subdir):
        raise AuthoringError(f"{path}.asset_subdir is unsafe")
    dice = request.get("dice")
    if dice is not None:
        values = require_list(dice, f"{path}.source_request.dice")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise AuthoringError(f"{path}.source_request.dice must contain integers or be null")
    return {
        "id": view["analysis_key"],
        "analysis_kind": kind,
        "title": display["title"],
        "subtitle": display["subtitle"],
        "fixture": True,
        "original_board": {
            "image": f"{public_asset_root}/{subdir}/starting.svg",
            "alt": display["original_board_alt"],
        },
        "context": {
            "score": None,
            "cube": None,
            "dice": "-".join(str(value) for value in dice) if dice is not None else None,
            "decision": display["decision"],
        },
        "metadata": {
            "engine": engine["name"],
            "engine_version": engine["version"],
            "source_family": "backgammon-node exact lesson analysis",
            "parser": provenance["parser"]["identity"],
            "provenance": (
                f"analysis {view['analysis_key']}; producer "
                f"{provenance['producer_identity_sha256']}"
            ),
            "analysis_settings": {"requested": requested, "effective": effective},
        },
        "probabilities": map_probabilities(view["probabilities"], f"{path}.probabilities"),
        "warnings": copy.deepcopy(view["warnings"]),
        "limitations": copy.deepcopy(view["limitations"]),
        "local_authoring": {
            "authority": LOCAL_AUTHORITY,
            "source_schema": view["schema_version"],
            "analysis_key": view["analysis_key"],
            "artifact_sha256": artifact_hash,
            "source_request": copy.deepcopy(request),
            "producer_provenance": copy.deepcopy(provenance),
        },
    }


def format_candidate_alt(template: str, rank: int, notation: str, path: str) -> str:
    try:
        value = template.format(rank=rank, notation=notation)
    except (KeyError, ValueError) as error:
        raise AuthoringError(
            f"{path}.presentation.candidate_alt has an unsupported placeholder"
        ) from error
    return require_text(value, f"{path}.presentation.candidate_alt")


def checker_model(
    view: dict[str, Any], selection: dict[str, Any], public_asset_root: str,
    artifact_hash: str, path: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    require_keys(view, ("checker", "played_move"), path)
    model = common_model(view, selection, public_asset_root, artifact_hash, path)
    display = presentation(selection, path)
    recommendation = require_object(view["recommendation"], f"{path}.recommendation")
    model["metadata"]["recommendation"] = require_text(
        recommendation.get("notation"), f"{path}.recommendation.notation"
    )
    model["metadata"]["played_move"] = optional_text(view.get("played_move"), f"{path}.played_move")
    checker = require_object(view.get("checker"), f"{path}.checker")
    rows = require_list(checker.get("candidates"), f"{path}.checker.candidates")
    if not rows:
        raise AuthoringError(f"{path}.checker.candidates must not be empty")
    candidates: list[dict[str, Any]] = []
    render_rows: list[dict[str, Any]] = []
    ids: set[str] = set()
    source_orders: set[int] = set()
    display_orders: set[int] = set()
    subdir = selection["asset_subdir"]
    detail_overlay = require_text(display.get("overlay_details"), f"{path}.presentation.overlay_details")
    detail_unsupported = require_text(display.get("unsupported_details"), f"{path}.presentation.unsupported_details")
    alt_template = require_text(display.get("candidate_alt"), f"{path}.presentation.candidate_alt")
    for index, item in enumerate(rows):
        item_path = f"{path}.checker.candidates[{index}]"
        row = require_object(item, item_path)
        require_keys(
            row,
            ("id", "source_order", "display_order", "notation", "evaluation", "value", "difference_from_best", "probabilities", "resulting_position_id"),
            item_path,
        )
        candidate_id = require_text(row["id"], f"{item_path}.id")
        source_order = optional_integer(row["source_order"], f"{item_path}.source_order")
        rank = optional_integer(row["display_order"], f"{item_path}.display_order")
        if candidate_id in ids or source_order is None or source_order < 1 or source_order in source_orders:
            raise AuthoringError(f"{item_path} has duplicate/invalid identity or source order")
        if rank is None or rank < 1 or rank in display_orders:
            raise AuthoringError(f"{item_path}.display_order must be unique and positive")
        ids.add(candidate_id); source_orders.add(source_order); display_orders.add(rank)
        notation = require_text(row["notation"], f"{item_path}.notation")
        evaluation = require_object(row["evaluation"], f"{item_path}.evaluation")
        require_keys(evaluation, ("type", "ply"), f"{item_path}.evaluation")
        value = require_object(row["value"], f"{item_path}.value")
        require_keys(value, ("label", "value"), f"{item_path}.value")
        mapped_value = {
            "label": require_text(value["label"], f"{item_path}.value.label"),
            "value": optional_number(value["value"], f"{item_path}.value.value"),
        }
        overlay = simple_overlay_supported(notation)
        filename = f"candidate-{rank}.svg" if overlay else None
        candidates.append({
            "id": candidate_id,
            "source_order": source_order,
            "display_rank": rank,
            "move": notation,
            "evaluation": require_text(evaluation["type"], f"{item_path}.evaluation.type"),
            "actual_ply": optional_integer(evaluation["ply"], f"{item_path}.evaluation.ply"),
            "value": mapped_value,
            "difference_from_best": optional_number(row["difference_from_best"], f"{item_path}.difference_from_best"),
            "probabilities": map_probabilities(row["probabilities"], f"{item_path}.probabilities"),
            "move_board": ({
                "image": f"{public_asset_root}/{subdir}/{filename}",
                "alt": format_candidate_alt(alt_template, rank, notation, path),
            } if filename else None),
            "resulting_position_id": optional_text(row["resulting_position_id"], f"{item_path}.resulting_position_id"),
            "details": detail_overlay if overlay else detail_unsupported,
        })
        render_rows.append({"id": candidate_id, "notation": notation, "filename": filename})
    model["candidates"] = sorted(candidates, key=lambda row: (row["display_rank"], row["source_order"], row["id"]))
    return model, render_rows


def cube_model(
    view: dict[str, Any], selection: dict[str, Any], public_asset_root: str,
    artifact_hash: str, path: str,
) -> tuple[dict[str, Any], bool]:
    require_keys(view, ("cube",), path)
    model = common_model(view, selection, public_asset_root, artifact_hash, path)
    display = presentation(selection, path)
    recommendation = require_object(view["recommendation"], f"{path}.recommendation")
    model["metadata"]["recommendation"] = require_text(recommendation.get("label"), f"{path}.recommendation.label")
    cube = require_object(view.get("cube"), f"{path}.cube")
    rows = require_list(cube.get("actions"), f"{path}.cube.actions")
    if not rows:
        raise AuthoringError(f"{path}.cube.actions must not be empty")
    actions: list[dict[str, Any]] = []
    ids: set[str] = set()
    source_orders: set[int] = set()
    display_orders: set[int] = set()
    details = require_text(display.get("action_details"), f"{path}.presentation.action_details")
    for index, item in enumerate(rows):
        item_path = f"{path}.cube.actions[{index}]"
        row = require_object(item, item_path)
        require_keys(row, ("id", "source_order", "display_order", "label", "normalized_action", "supported", "value", "probabilities"), item_path)
        action_id = require_text(row["id"], f"{item_path}.id")
        source_order = optional_integer(row["source_order"], f"{item_path}.source_order")
        display_order = optional_integer(row["display_order"], f"{item_path}.display_order")
        if action_id in ids or source_order is None or source_order < 1 or source_order in source_orders:
            raise AuthoringError(f"{item_path} has duplicate/invalid identity or source order")
        if display_order is None or display_order < 1 or display_order in display_orders:
            raise AuthoringError(f"{item_path}.display_order must be unique and positive")
        if not isinstance(row["supported"], bool):
            raise AuthoringError(f"{item_path}.supported must be boolean")
        ids.add(action_id); source_orders.add(source_order); display_orders.add(display_order)
        value = require_object(row["value"], f"{item_path}.value")
        require_keys(value, ("label", "value"), f"{item_path}.value")
        actions.append({
            "id": action_id,
            "label": require_text(row["label"], f"{item_path}.label"),
            "normalized_action": require_text(row["normalized_action"], f"{item_path}.normalized_action"),
            "supported": row["supported"],
            "value": {
                "label": require_text(value["label"], f"{item_path}.value.label"),
                "value": optional_number(value["value"], f"{item_path}.value.value"),
            },
            "probabilities": map_probabilities(row["probabilities"], f"{item_path}.probabilities"),
            "details": details,
            "_sort": (display_order, source_order, action_id),
        })
    actions.sort(key=lambda action: action["_sort"])
    for action in actions:
        action.pop("_sort")
    model["actions"] = actions
    responder = display.get("render_responder_board", False)
    if not isinstance(responder, bool):
        raise AuthoringError(f"{path}.presentation.render_responder_board must be boolean")
    if responder:
        model["responder_board"] = {
            "image": f"{public_asset_root}/{selection['asset_subdir']}/responder.svg",
            "alt": require_text(display.get("responder_board_alt"), f"{path}.presentation.responder_board_alt"),
        }
    return model, responder


def build_document(config: dict[str, Any], repo_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Path]]:
    require_keys(config, ("schema_version", "authority", "slug", "output", "fixture_status", "analyses"), "config")
    if config["schema_version"] != CONFIG_SCHEMA or config["authority"] != LOCAL_AUTHORITY:
        raise AuthoringError("Config must explicitly declare the local-development-only schema and authority")
    slug = require_text(config["slug"], "config.slug")
    if not SLUG.fullmatch(slug):
        raise AuthoringError("config.slug must be a lowercase hyphenated slug")
    output = require_object(config["output"], "config.output")
    require_keys(output, ("analysis_view", "assets", "public_asset_root"), "config.output")
    view_path = resolve_path(output["analysis_view"], repo_root, "config.output.analysis_view")
    assets_path = resolve_path(output["assets"], repo_root, "config.output.assets")
    if assets_path in {Path(assets_path.anchor), Path.home().resolve(), repo_root}:
        raise AuthoringError("config.output.assets must not target a broad directory")
    public_root = require_text(output["public_asset_root"], "config.output.public_asset_root").rstrip("/")
    if not public_root.startswith("/") or ".." in public_root.split("/"):
        raise AuthoringError("config.output.public_asset_root must be a safe root-relative URL")
    status = require_object(config["fixture_status"], "config.fixture_status")
    require_keys(status, ("kind", "label", "message"), "config.fixture_status")
    if status["kind"] != "retained-analysis":
        raise AuthoringError("Local Node authoring output must remain retained-analysis, not Canonical")
    fixture_status = {key: require_text(status[key], f"config.fixture_status.{key}") for key in ("kind", "label", "message")}
    selections = require_list(config["analyses"], "config.analyses")
    if not selections:
        raise AuthoringError("config.analyses must not be empty")
    analyses: dict[str, Any] = {}
    render_analyses: list[dict[str, Any]] = []
    artifact_paths: dict[str, Path] = {}
    subdirs: set[str] = set()
    for index, raw in enumerate(selections):
        path = f"config.analyses[{index}]"
        selection = require_object(raw, path)
        require_keys(selection, ("artifact", "analysis_id", "kind", "asset_subdir", "presentation"), path)
        artifact = resolve_path(selection["artifact"], repo_root, f"{path}.artifact")
        view = load_json(artifact)
        validate_common(view, selection, path)
        analysis_id = selection["analysis_id"]
        if analysis_id in analyses:
            raise AuthoringError(f"Duplicate selected analysis identity: {analysis_id}")
        subdir = selection["asset_subdir"]
        if subdir in subdirs:
            raise AuthoringError(f"Duplicate asset_subdir: {subdir}")
        subdirs.add(subdir)
        artifact_hash = file_sha256(artifact)
        if selection["kind"] == "checker":
            model, candidates = checker_model(view, selection, public_root, artifact_hash, path)
            render_entry = {"candidates": candidates, "render_responder_board": False}
        else:
            model, responder = cube_model(view, selection, public_root, artifact_hash, path)
            render_entry = {"candidates": [], "render_responder_board": responder}
        analyses[analysis_id] = model
        artifact_paths[analysis_id] = artifact
        render_analyses.append({
            "analysis_id": analysis_id,
            "kind": selection["kind"],
            "artifact": str(artifact),
            "artifact_sha256": artifact_hash,
            "asset_subdir": subdir,
            **render_entry,
        })
    document = {
        "schema_version": VIEWER_SCHEMA,
        "fixture_status": fixture_status,
        "analyses": {key: analyses[key] for key in sorted(analyses)},
        "local_authoring": {
            "authority": LOCAL_AUTHORITY,
            "slug": slug,
            "message": "Rebuildable local Node projection; not Canonical analytical authority.",
        },
    }
    manifest = {"schema_version": CONFIG_SCHEMA, "authority": LOCAL_AUTHORITY, "slug": slug, "analyses": render_analyses}
    return document, manifest, {"view": view_path, "assets": assets_path}


def marker(binding_name: str, side: str) -> str:
    return f"<!-- bs-local-node-analysis:{binding_name}:{side} -->"


def binding_block(binding: dict[str, Any], public_view_url: str) -> str:
    name = require_text(binding.get("name"), "learn_binding.name")
    if not SLUG.fullmatch(name):
        raise AuthoringError("learn_binding.name must be a lowercase hyphenated slug")
    kind = require_text(binding.get("kind"), f"learn_binding[{name}].kind")
    analysis_id = require_text(binding.get("analysis_id"), f"learn_binding[{name}].analysis_id")
    title = require_text(binding.get("title"), f"learn_binding[{name}].title")
    prompt = require_text(binding.get("prompt"), f"learn_binding[{name}].prompt")
    if any('"' in value or "\n" in value for value in (title, prompt, analysis_id)):
        raise AuthoringError(f"learn_binding[{name}] attributes must not contain quotes/newlines")
    attrs = [
        'class="bs-lesson-analysis-host"',
        f"data-bs-{kind}-decision",
        f'data-bs-analysis-src="{public_view_url}"',
        f'data-bs-analysis-id="{analysis_id}"',
        f'data-bs-lesson-title="{title}"',
        f'data-bs-lesson-prompt="{prompt}"',
    ]
    if kind == "cube":
        action_ids = require_object(binding.get("action_ids"), f"learn_binding[{name}].action_ids")
        for config_key, attr in (
            ("no_double", "data-bs-no-double-action-id"),
            ("double_take", "data-bs-double-take-action-id"),
            ("double_pass", "data-bs-double-pass-action-id"),
        ):
            attrs.append(f'{attr}="{require_text(action_ids.get(config_key), f"learn_binding[{name}].action_ids.{config_key}")}"')
    elif kind != "checker":
        raise AuthoringError(f"learn_binding[{name}].kind is unsupported")
    lines = [marker(name, "start"), "<div"] + [f"  {attr}" for attr in attrs] + ["></div>", marker(name, "end")]
    return "\n".join(lines)


def apply_learn_bindings(config: dict[str, Any], repo_root: Path, analysis_ids: set[str]) -> list[Path]:
    bindings = config.get("learn_bindings", [])
    rows = require_list(bindings, "config.learn_bindings")
    if not rows:
        return []
    output = require_object(config["output"], "config.output")
    public_view_url = require_text(output.get("public_analysis_view"), "config.output.public_analysis_view")
    if not public_view_url.startswith("/") or ".." in public_view_url.split("/"):
        raise AuthoringError("config.output.public_analysis_view must be a safe root-relative URL")
    changed: list[Path] = []
    seen_lessons: set[Path] = set()
    for index, raw in enumerate(rows):
        path = f"config.learn_bindings[{index}]"
        binding = require_object(raw, path)
        require_keys(binding, ("name", "lesson", "kind", "analysis_id", "title", "prompt"), path)
        if binding["analysis_id"] not in analysis_ids:
            raise AuthoringError(f"{path} refers to an analysis not selected by this config")
        lesson = resolve_path(binding["lesson"], repo_root, f"{path}.lesson")
        if lesson in seen_lessons:
            raise AuthoringError(f"Multiple bindings for one lesson are ambiguous: {lesson}")
        seen_lessons.add(lesson)
        try:
            source = lesson.read_text(encoding="utf-8")
        except OSError as error:
            raise AuthoringError(f"Unable to read Learn lesson {lesson}: {error}") from error
        generated = binding_block(binding, public_view_url)
        start = marker(binding["name"], "start")
        end = marker(binding["name"], "end")
        if source.count(start) != 1 or source.count(end) != 1:
            raise AuthoringError(f"{path} requires exactly one marked Learn binding region")
        before, remainder = source.split(start, 1)
        _, after = remainder.split(end, 1)
        updated = before + generated + after
        if updated != source:
            write_atomic(lesson, updated.encode("utf-8"))
            changed.append(lesson)
    return changed


def expected_assets(document: dict[str, Any]) -> set[Path]:
    expected = {Path("PROVENANCE.txt")}
    for model in document["analyses"].values():
        subdir = Path(model["original_board"]["image"]).parent.name
        expected.add(Path(subdir) / "starting.svg")
        if model["analysis_kind"] == "checker":
            for candidate in model["candidates"]:
                if candidate["move_board"]:
                    expected.add(Path(subdir) / Path(candidate["move_board"]["image"]).name)
        elif model.get("responder_board"):
            expected.add(Path(subdir) / "responder.svg")
    return expected


def render_assets(manifest: dict[str, Any], document: dict[str, Any], assets_path: Path, repo_root: Path) -> None:
    assets_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{assets_path.name}.", dir=assets_path.parent) as name:
        stage = Path(name) / "assets"
        stage.mkdir()
        render_manifest = copy.deepcopy(manifest)
        render_manifest["output_root"] = str(stage)
        manifest_path = Path(name) / "render-manifest.json"
        manifest_path.write_bytes(stable_bytes(render_manifest))
        environment = dict(os.environ)
        default_library = repo_root / ".r-library"
        if default_library.is_dir():
            inherited = environment.get("R_LIBS_USER")
            environment["R_LIBS_USER"] = (
                str(default_library)
                if not inherited
                else os.pathsep.join((str(default_library), inherited))
            )
        executable = environment.get("RSCRIPT_BIN", "Rscript")
        command = [executable, "--vanilla", str(repo_root / "scripts/analysis/render_node_analysis_assets.R"), str(manifest_path)]
        try:
            subprocess.run(command, cwd=repo_root, env=environment, check=True)
        except (OSError, subprocess.CalledProcessError) as error:
            raise AuthoringError(f"Build-time board rendering failed: {error}") from error
        changed_artifacts = [
            entry["analysis_id"]
            for entry in manifest["analyses"]
            if file_sha256(Path(entry["artifact"])) != entry["artifact_sha256"]
        ]
        if changed_artifacts:
            raise AuthoringError(
                "Node artifact changed during materialization: "
                + ", ".join(changed_artifacts)
            )
        missing = sorted(path for path in expected_assets(document) if not (stage / path).is_file())
        if missing:
            raise AuthoringError(f"Board renderer omitted expected asset(s): {missing}")
        backup = Path(name) / "previous-assets"
        try:
            if assets_path.exists():
                os.replace(assets_path, backup)
            os.replace(stage, assets_path)
        except Exception:
            if backup.exists() and not assets_path.exists():
                os.replace(backup, assets_path)
            raise
        if backup.exists():
            shutil.rmtree(backup)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="local Node authoring config JSON")
    parser.add_argument("--project-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    try:
        config = load_json(args.config.resolve())
        document, manifest, paths = build_document(config, repo_root)
        repeated, repeated_manifest, repeated_paths = build_document(config, repo_root)
        if stable_bytes(document) != stable_bytes(repeated) or manifest != repeated_manifest or paths != repeated_paths:
            raise AuthoringError("Repeat projection was not deterministic")
        if not args.project_only:
            render_assets(manifest, document, paths["assets"], repo_root)
        write_atomic(paths["view"], stable_bytes(document))
        changed = [] if args.project_only else apply_learn_bindings(config, repo_root, set(document["analyses"]))
    except AuthoringError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"PASS: materialized local Node analysis view: {paths['view']}")
    if args.project_only:
        print("NOTE: project-only test mode skipped board assets and Learn bindings")
    else:
        print(f"PASS: prepared build-time board assets: {paths['assets']}")
        print(f"PASS: Learn bindings checked: {len(config.get('learn_bindings', []))}; changed: {len(changed)}")
    print("AUTHORITY: local-development-only; this output is not Canonical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
