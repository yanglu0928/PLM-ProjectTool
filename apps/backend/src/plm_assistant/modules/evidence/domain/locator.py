"""Typed EvidenceLocator validation; no document resolution or authorization.

The validated payload is an internal DTO. Only a later authorized resolver can
claim that a locator actually points to content in a fixed DocumentVersion.
"""

from __future__ import annotations

import math
import re
import uuid
from collections.abc import Mapping


_FINGERPRINT = re.compile(r"[0-9a-fA-F]{64}\Z")
_A1_CELL = re.compile(r"([A-Za-z]{1,3})([1-9][0-9]{0,6})\Z")


class EvidenceLocatorError(ValueError):
    """The locator is not a supported, reproducible typed position."""


def validate_evidence_locator(raw: object) -> dict[str, object]:
    """Return a canonical copy of one of the nine frozen locator variants."""
    if not isinstance(raw, Mapping) or not all(type(key) is str for key in raw):
        raise EvidenceLocatorError("invalid evidence locator")
    kind = raw.get("locator_type")
    if type(kind) is not str:
        raise EvidenceLocatorError("invalid evidence locator type")

    if kind == "DOCUMENT":
        _keys(raw, {"locator_type"})
        return {"locator_type": kind}
    if kind == "PAGE":
        _keys(raw, {"locator_type", "page_no", "bbox"}, {"page_no"})
        result: dict[str, object] = {"locator_type": kind, "page_no": _positive(raw["page_no"])}
        if "bbox" in raw:
            result["bbox"] = _box(raw["bbox"])
        return result
    if kind == "TEXT_RANGE":
        _keys(raw, {"locator_type", "page_no", "section_path", "start_offset",
                    "end_offset", "normalized_fingerprint"},
              {"start_offset", "end_offset", "normalized_fingerprint"})
        if ("page_no" in raw) == ("section_path" in raw):
            raise EvidenceLocatorError("text range requires one source position")
        start = _nonnegative(raw["start_offset"])
        end = _positive(raw["end_offset"])
        if end <= start:
            raise EvidenceLocatorError("invalid text range")
        fingerprint = raw["normalized_fingerprint"]
        if type(fingerprint) is not str or _FINGERPRINT.fullmatch(fingerprint) is None:
            raise EvidenceLocatorError("invalid text fingerprint")
        result = {"locator_type": kind, "start_offset": start, "end_offset": end,
                  "normalized_fingerprint": fingerprint.lower()}
        if "page_no" in raw:
            result["page_no"] = _positive(raw["page_no"])
        else:
            result["section_path"] = _label(raw["section_path"], 1024)
        return result
    if kind == "SECTION":
        _keys(raw, {"locator_type", "section_path"}, {"section_path"})
        return {"locator_type": kind, "section_path": _label(raw["section_path"], 1024)}
    if kind == "PARAGRAPH":
        _keys(raw, {"locator_type", "page_no", "paragraph_index", "stable_anchor"})
        if ("paragraph_index" in raw) == ("stable_anchor" in raw):
            raise EvidenceLocatorError("paragraph requires one stable position")
        result = {"locator_type": kind}
        if "page_no" in raw:
            result["page_no"] = _positive(raw["page_no"])
        if "paragraph_index" in raw:
            result["paragraph_index"] = _positive(raw["paragraph_index"])
        else:
            result["stable_anchor"] = _label(raw["stable_anchor"], 256)
        return result
    if kind == "TABLE_CELL":
        _keys(raw, {"locator_type", "table_anchor", "row_no", "column_no"},
              {"table_anchor", "row_no", "column_no"})
        return {"locator_type": kind, "table_anchor": _label(raw["table_anchor"], 256),
                "row_no": _positive(raw["row_no"]), "column_no": _positive(raw["column_no"])}
    if kind == "SHEET_RANGE":
        _keys(raw, {"locator_type", "sheet_name", "start_cell", "end_cell"},
              {"sheet_name", "start_cell", "end_cell"})
        start = _cell(raw["start_cell"])
        end = _cell(raw["end_cell"])
        if end[0] < start[0] or end[1] < start[1]:
            raise EvidenceLocatorError("invalid sheet range")
        return {"locator_type": kind, "sheet_name": _label(raw["sheet_name"], 128),
                "start_cell": start[2], "end_cell": end[2]}
    if kind == "SLIDE_SHAPE":
        _keys(raw, {"locator_type", "slide_no", "shape_id", "bounds"},
              {"slide_no", "shape_id"})
        result = {"locator_type": kind, "slide_no": _positive(raw["slide_no"]),
                  "shape_id": _label(raw["shape_id"], 256)}
        if "bounds" in raw:
            result["bounds"] = _box(raw["bounds"])
        return result
    if kind == "STRUCTURED_NODE":
        _keys(raw, {"locator_type", "parse_record_id", "node_id", "source_locator"},
              {"parse_record_id", "node_id", "source_locator"})
        try:
            parsed_id = uuid.UUID(raw["parse_record_id"])
        except (TypeError, ValueError, AttributeError):
            raise EvidenceLocatorError("invalid parse record reference") from None
        source = raw["source_locator"]
        if not isinstance(source, Mapping) or source.get("locator_type") == "STRUCTURED_NODE":
            raise EvidenceLocatorError("invalid structured source position")
        return {"locator_type": kind, "parse_record_id": str(parsed_id),
                "node_id": _label(raw["node_id"], 256),
                "source_locator": validate_evidence_locator(source)}
    raise EvidenceLocatorError("unsupported evidence locator type")


def _keys(raw: Mapping[str, object], allowed: set[str], required: set[str] | None = None) -> None:
    if not set(raw).issubset(allowed) or not (required or set()).issubset(raw):
        raise EvidenceLocatorError("invalid evidence locator fields")


def _positive(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise EvidenceLocatorError("invalid positive position")
    return value


def _nonnegative(value: object) -> int:
    if type(value) is not int or value < 0:
        raise EvidenceLocatorError("invalid position")
    return value


def _label(value: object, maximum: int) -> str:
    if type(value) is not str or not value or len(value) > maximum or value != value.strip():
        raise EvidenceLocatorError("invalid position label")
    if any(ord(char) < 32 for char in value):
        raise EvidenceLocatorError("invalid position label")
    return value


def _box(value: object) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise EvidenceLocatorError("invalid position bounds")
    if any(type(item) not in (int, float) or not math.isfinite(item)
           or item < 0 or item > 1 for item in value):
        raise EvidenceLocatorError("invalid position bounds")
    left, top, right, bottom = value
    if left >= right or top >= bottom:
        raise EvidenceLocatorError("invalid position bounds")
    return [float(item) for item in value]


def _cell(value: object) -> tuple[int, int, str]:
    if type(value) is not str:
        raise EvidenceLocatorError("invalid sheet cell")
    match = _A1_CELL.fullmatch(value)
    if match is None:
        raise EvidenceLocatorError("invalid sheet cell")
    column = 0
    for char in match.group(1).upper():
        column = column * 26 + ord(char) - ord("A") + 1
    row = int(match.group(2))
    if column > 16384 or row > 1048576:
        raise EvidenceLocatorError("invalid sheet cell")
    return column, row, f"{match.group(1).upper()}{row}"
