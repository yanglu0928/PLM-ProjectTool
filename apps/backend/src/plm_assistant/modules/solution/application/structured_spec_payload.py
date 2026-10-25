"""Pure, bounded SOL-06 payload validation; not a source or approval proof."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, field


MAX_PAYLOAD_BYTES = 1_000_000  # below the 0163 JSONB 1 MiB ceiling
MAX_ITEMS = 500


class StructuredSpecPayloadError(RuntimeError):
    def __init__(self, code: str = "VALIDATION_FAILED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ValidatedStructuredSpecPayload:
    spec_type: str
    schema_version: int
    payload_json: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)

    def payload(self) -> dict[str, object]:
        """Return a fresh copy; callers cannot mutate the validated snapshot."""
        return json.loads(self.payload_json)


def _fail() -> None:
    raise StructuredSpecPayloadError()


def _shape(value: object, keys: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != keys or any(type(k) is not str for k in value):
        _fail()
    return value


def _text(value: object, *, limit: int = 500) -> str:
    if (type(value) is not str or not 1 <= len(value) <= limit
            or value != value.strip() or value != unicodedata.normalize("NFC", value)
            or any(unicodedata.category(char) in ("Cc", "Cs") for char in value)):
        _fail()
    return value


def _items(value: object, *, minimum: int = 0, maximum: int = MAX_ITEMS) -> list[object]:
    if type(value) is not list or not minimum <= len(value) <= maximum:
        _fail()
    return value


def _strings(value: object, *, minimum: int = 0) -> list[str]:
    items = [_text(item) for item in _items(value, minimum=minimum)]
    if len(set(items)) != len(items):
        _fail()
    return items


def _base(payload: dict[str, object]) -> None:
    _strings(payload["assumptions"])
    _strings(payload["exclusions"])


def _strict_json(value: object, depth: int = 0) -> None:
    if depth > 32:
        _fail()
    if type(value) is dict:
        if len(value) > 5000:
            _fail()
        for key, item in value.items():
            if type(key) is not str or len(key) > 128:
                _fail()
            _strict_json(item, depth + 1)
    elif type(value) is list:
        if len(value) > 5000:
            _fail()
        for item in value:
            _strict_json(item, depth + 1)
    elif type(value) is str:
        if len(value) > MAX_PAYLOAD_BYTES:
            _fail()
    elif type(value) not in (str, int, float, bool, type(None)):
        _fail()


def _process(payload: dict[str, object]) -> None:
    _shape(payload, {"nodes", "edges", "assumptions", "exclusions"})
    _base(payload)
    nodes = _items(payload["nodes"], minimum=2)
    if len(nodes) > 200:
        _fail()
    ids: set[str] = set()
    starts: set[str] = set()
    ends: set[str] = set()
    for raw in nodes:
        node = _shape(raw, {"id", "kind", "role", "inputs", "outputs"})
        node_id = _text(node["id"], limit=128)
        kind = node["kind"]
        if node_id in ids or kind not in ("START", "STEP", "END") or type(kind) is not str:
            _fail()
        ids.add(node_id)
        if kind == "START":
            starts.add(node_id)
        elif kind == "END":
            ends.add(node_id)
        _text(node["role"], limit=128)
        _strings(node["inputs"])
        _strings(node["outputs"])
    if len(starts) != 1 or not ends:
        _fail()
    edges: set[tuple[str, str]] = set()
    graph: dict[str, set[str]] = {node_id: set() for node_id in ids}
    incoming: dict[str, int] = {node_id: 0 for node_id in ids}
    for raw in _items(payload["edges"], minimum=1):
        edge = _shape(raw, {"from", "to"})
        source, target = _text(edge["from"], limit=128), _text(edge["to"], limit=128)
        if (source not in ids or target not in ids or source == target
                or (source, target) in edges or source in ends or target in starts):
            _fail()
        edges.add((source, target))
        graph[source].add(target)
        incoming[target] += 1
    start = next(iter(starts))
    if incoming[start] or any(graph[end] for end in ends):
        _fail()
    reached = {start}
    frontier = [start]
    while frontier:
        for next_id in graph[frontier.pop()] - reached:
            reached.add(next_id)
            frontier.append(next_id)
    if reached != ids or any(incoming[node_id] == 0 for node_id in ids - starts):
        _fail()
    reverse: dict[str, set[str]] = {node_id: set() for node_id in ids}
    for source, target in edges:
        reverse[target].add(source)
    can_reach_end = set(ends)
    frontier = list(ends)
    while frontier:
        for prior in reverse[frontier.pop()] - can_reach_end:
            can_reach_end.add(prior)
            frontier.append(prior)
    if can_reach_end != ids:
        _fail()


def _interface(payload: dict[str, object]) -> None:
    _shape(payload, {"source_system", "target_system", "direction", "data_owner",
                     "frequency", "error_handling", "retry_policy", "authentication",
                     "field_mappings", "assumptions", "exclusions"})
    _base(payload)
    _text(payload["source_system"])
    _text(payload["target_system"])
    if type(payload["direction"]) is not str or payload["direction"] not in (
            "INBOUND", "OUTBOUND", "BIDIRECTIONAL"):
        _fail()
    for key in ("data_owner", "frequency", "error_handling", "retry_policy", "authentication"):
        _text(payload[key], limit=2000)
    pairs: set[tuple[str, str]] = set()
    for raw in _items(payload["field_mappings"], minimum=1):
        mapping = _shape(raw, {"source", "target"})
        pair = (_text(mapping["source"]), _text(mapping["target"]))
        if pair in pairs:
            _fail()
        pairs.add(pair)


def _migration(payload: dict[str, object]) -> None:
    _shape(payload, {"source_system", "target_system", "scope", "cleansing_rules",
                     "field_mappings", "trial_plan", "reconciliation_plan",
                     "rollback_plan", "acceptance_criteria", "assumptions", "exclusions"})
    _base(payload)
    _text(payload["source_system"])
    _text(payload["target_system"])
    for key in ("scope", "trial_plan", "reconciliation_plan", "rollback_plan",
                "acceptance_criteria"):
        _text(payload[key], limit=2000)
    _strings(payload["cleansing_rules"], minimum=1)
    pairs: set[tuple[str, str]] = set()
    for raw in _items(payload["field_mappings"], minimum=1):
        mapping = _shape(raw, {"source", "target"})
        pair = (_text(mapping["source"]), _text(mapping["target"]))
        if pair in pairs:
            _fail()
        pairs.add(pair)


def _permission(payload: dict[str, object]) -> None:
    _shape(payload, {"roles", "resources", "grants", "default_deny",
                     "separation_policy", "separation_of_duties",
                     "assumptions", "exclusions"})
    _base(payload)
    roles = set(_strings(payload["roles"], minimum=1))
    resources = set(_strings(payload["resources"], minimum=1))
    if payload["default_deny"] is not True:
        _fail()
    _text(payload["separation_policy"], limit=2000)
    grants: set[tuple[str, str, str, str]] = set()
    for raw in _items(payload["grants"], minimum=1):
        grant = _shape(raw, {"role", "resource", "action", "scope"})
        row = tuple(_text(grant[key]) for key in ("role", "resource", "action", "scope"))
        if row[0] not in roles or row[1] not in resources or row in grants:
            _fail()
        grants.add(row)
    pairs: set[frozenset[str]] = set()
    for raw in _items(payload["separation_of_duties"]):
        separation = _shape(raw, {"left_role", "right_role"})
        left, right = _text(separation["left_role"]), _text(separation["right_role"])
        pair = frozenset((left, right))
        if left == right or left not in roles or right not in roles or pair in pairs:
            _fail()
        pairs.add(pair)


_VALIDATORS = {
    "PROCESS_MODEL": _process,
    "INTERFACE_SPEC": _interface,
    "MIGRATION_SPEC": _migration,
    "PERMISSION_DESIGN": _permission,
}


def validate_structured_spec_payload(
    spec_type: object, payload: object, *, schema_version: object = 1,
) -> ValidatedStructuredSpecPayload:
    """Validate a fresh snapshot; never infer current source or review eligibility."""
    if type(spec_type) is not str or spec_type not in _VALIDATORS or type(schema_version) is not int or schema_version != 1:
        _fail()
    try:
        _strict_json(payload)
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(raw) > MAX_PAYLOAD_BYTES:
            _fail()
        copied = json.loads(raw)
        _VALIDATORS[spec_type](copied)
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError):
        raise StructuredSpecPayloadError() from None
    return ValidatedStructuredSpecPayload(
        spec_type=spec_type, schema_version=1, payload_json=raw,
        payload_fingerprint=hashlib.sha256(raw).digest(),
    )
