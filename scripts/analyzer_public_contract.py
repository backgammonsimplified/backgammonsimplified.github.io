#!/usr/bin/env python3
"""Gateway-neutral validation for the Analyzer public HTTP contract.

This module deliberately has no Node launcher, shell transport, queue, cache,
database, or request-identity implementation.  A future production gateway can
use this boundary before handing the normalized submission to the authoritative
backgammon-node service.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable
from urllib.parse import urlsplit


REQUEST_SCHEMA = "bms-analysis-submission-v2"
SUBMIT_RESPONSE_SCHEMA = "bms-analyzer-public-submit-v1"
STATUS_RESPONSE_SCHEMA = "bms-analyzer-public-status-v1"
RESULT_RESPONSE_SCHEMA = "bms-analyzer-public-result-v1"
ERROR_RESPONSE_SCHEMA = "bms-analyzer-public-error-v1"
ANALYSIS_VIEW_SCHEMA = "bms-node-analysis-view-v0"
MAX_REQUEST_BYTES = 2_048
ANALYSIS_KEY = re.compile(r"^sha256-[0-9a-f]{64}$")
GNU_ID = re.compile(r"^[A-Za-z0-9+/]{14}:[A-Za-z0-9+/]{12}$")

ACTIVE_STATES = {"queued", "running"}
FAILURE_STATES = {
    "cancelled",
    "failed",
    "timed_out",
    "unsupported",
    "configuration_mismatch",
}
PUBLIC_STATES = {*ACTIVE_STATES, *FAILURE_STATES, "complete"}

PUBLIC_ERROR_MESSAGES = {
    "malformed_request": "The analysis request is invalid.",
    "request_too_large": "The analysis request is too large.",
    "unsupported_capability": "That analysis capability is not available.",
    "unknown_analysis": "That analysis request was not found.",
    "rate_limited": "Too many analysis requests. Try again later.",
    "cancelled": "The analysis request was cancelled.",
    "failed": "The analysis could not be completed.",
    "timed_out": "The analysis timed out.",
    "unsupported": "That analysis capability is not available.",
    "configuration_mismatch": "The analysis service is temporarily unavailable.",
    "node_unavailable": "The analysis service is temporarily unavailable.",
    "service_unavailable": "The analysis service is temporarily unavailable.",
}


class ContractError(ValueError):
    """A public-safe contract rejection."""

    def __init__(self, code: str, message: str, http_status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ContractError("malformed_request", f"{label} has unsupported fields.")


def parse_request_body(body: bytes) -> dict[str, Any]:
    """Decode one bounded UTF-8 JSON request and normalize its public fields."""

    if not body:
        raise ContractError("malformed_request", "The analysis request is empty.")
    if len(body) > MAX_REQUEST_BYTES:
        raise ContractError("request_too_large", PUBLIC_ERROR_MESSAGES["request_too_large"], 413)
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError("malformed_request", "The analysis request must be valid JSON.") from error
    return normalize_request(value)


def normalize_request(value: Any) -> dict[str, Any]:
    """Validate the exact website capability without computing Node identity."""

    if not isinstance(value, dict):
        raise ContractError("malformed_request", "The analysis request must be an object.")
    _exact_keys(
        value,
        {"schema_version", "engine", "decision_type", "analysis_setting", "position", "dice"},
        "The analysis request",
    )
    if value["schema_version"] != REQUEST_SCHEMA:
        raise ContractError("malformed_request", "The analysis request schema is unsupported.")
    if value["engine"] != "gnu" or value["analysis_setting"] != "1ply":
        raise ContractError(
            "unsupported_capability",
            PUBLIC_ERROR_MESSAGES["unsupported_capability"],
            422,
        )
    decision = value["decision_type"]
    if decision not in {"checker", "cube"}:
        raise ContractError("malformed_request", "The decision type is unsupported.")
    position = value["position"]
    if not isinstance(position, dict):
        raise ContractError("malformed_request", "The position must be a complete GNUID.")
    _exact_keys(position, {"format", "id"}, "The position")
    gnuid = position["id"]
    if position["format"] != "gnuid" or not isinstance(gnuid, str) or GNU_ID.fullmatch(gnuid) is None:
        raise ContractError("malformed_request", "The position must be a complete GNUID.")
    dice = value["dice"]
    if decision == "checker":
        if (
            not isinstance(dice, list)
            or len(dice) != 2
            or any(isinstance(die, bool) or not isinstance(die, int) or die < 1 or die > 6 for die in dice)
        ):
            raise ContractError("malformed_request", "Checker analysis requires two dice.")
        normalized_dice: list[int] | None = list(dice)
    else:
        if dice is not None:
            raise ContractError("malformed_request", "Cube analysis requires null dice.")
        normalized_dice = None
    return {
        "schema_version": REQUEST_SCHEMA,
        "engine": "gnu",
        "decision_type": decision,
        "analysis_setting": "1ply",
        "position": {"format": "gnuid", "id": gnuid},
        "dice": normalized_dice,
    }


def validate_analysis_key(value: Any) -> str:
    if not isinstance(value, str) or ANALYSIS_KEY.fullmatch(value) is None:
        raise ContractError("malformed_request", "The analysis key is invalid.")
    return value


def public_error(code: Any) -> dict[str, Any]:
    """Map any internal failure to a stable response without using internal text."""

    safe_code = code if isinstance(code, str) and code in PUBLIC_ERROR_MESSAGES else "service_unavailable"
    return {
        "schema_version": ERROR_RESPONSE_SCHEMA,
        "error": {"code": safe_code, "message": PUBLIC_ERROR_MESSAGES[safe_code]},
    }


def validate_origin(origin: str) -> str:
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ContractError("configuration_mismatch", "The allowed site origin is invalid.", 503)
    return f"https://{parsed.netloc}"


def cors_headers(origin: str | None, allowed_origins: Iterable[str]) -> dict[str, str]:
    """Return exact-origin CORS headers; wildcard origins are never accepted."""

    if origin is None:
        return {}
    allowed = {validate_origin(item) for item in allowed_origins}
    normalized = validate_origin(origin)
    if normalized not in allowed:
        raise ContractError("origin_denied", "This site origin is not allowed.", 403)
    return {
        "Access-Control-Allow-Origin": normalized,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "600",
        "Vary": "Origin",
    }


def _reject_private_text(value: Any) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _reject_private_text(item)
        return
    if isinstance(value, list):
        for item in value:
            _reject_private_text(item)
        return
    if not isinstance(value, str):
        return
    if (
        re.search(
            r"(?:\bssh\b|traceback|authorization:|bearer\s|private key|\b[A-Za-z0-9.-]+\.(?:internal|local)\b)",
            value,
            re.I,
        )
        or re.match(r"^[A-Za-z]:[\\/]", value)
        or re.match(r"^/(?:home|srv|etc|var|tmp|opt|root|mnt)/", value)
    ):
        raise ContractError("service_unavailable", "The analysis result is not public-safe.", 502)


def validate_public_result(value: Any, expected_key: str) -> dict[str, Any]:
    """Validate the public result envelope and Node-produced analysis view."""

    key = validate_analysis_key(expected_key)
    if not isinstance(value, dict):
        raise ContractError("service_unavailable", "The analysis result is malformed.", 502)
    if set(value) != {"schema_version", "analysis_key", "status", "analysis_view"}:
        raise ContractError("service_unavailable", "The analysis result is malformed.", 502)
    view = value.get("analysis_view")
    if (
        value.get("schema_version") != RESULT_RESPONSE_SCHEMA
        or value.get("analysis_key") != key
        or value.get("status") != "complete"
        or not isinstance(view, dict)
        or view.get("schema_version") != ANALYSIS_VIEW_SCHEMA
        or view.get("analysis_key") != key
    ):
        raise ContractError("service_unavailable", "The analysis result is malformed.", 502)
    _reject_private_text(view)
    return value
