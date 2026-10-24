"""Deterministic Windows proof for the gap-output.v2 trust boundary."""

from __future__ import annotations

import json

from plm_assistant.modules.ai.application.output_schema import (
    AIOutputSchemaError,
    default_ai_output_schema_registry,
)


def payload(node_id: str = "paragraph-2") -> dict[str, object]:
    return {
        "schema_ref": "gap-output.v2",
        "schema_version": 2,
        "items": [{
            "category": "PENDING_CONFIRMATION",
            "title": "接口回写范围",
            "summary": "调研记录没有固定回写对象和字段。",
            "rationale": "本次最小投影仅包含接口需求描述。",
            "recommendation": "请项目负责人补充回写范围。",
            "source_citations": [{
                "source_ordinal": 1,
                "node_ids": [node_id],
            }],
            "confirmation": {
                "required": True,
                "question": "接口需要回写哪些对象和字段？",
                "required_fields": [{
                    "key": "SCOPE",
                    "label": "回写范围",
                    "prompt": "请列出对象、字段和触发时点。",
                    "reason": "用于确认接口边界与失败补偿。",
                    "required": True,
                }],
            },
        }],
    }


def main() -> None:
    schema = default_ai_output_schema_registry().resolve("gap-output.v2", 2)
    allowed_ordinals = frozenset({1, 2})
    allowed_nodes = {
        1: frozenset({"heading-1", "paragraph-2"}),
        2: frozenset({"sheet-1-row-3"}),
    }
    result = schema.validate(
        payload(),
        allowed_source_ordinals=allowed_ordinals,
        allowed_source_nodes=allowed_nodes,
    )
    assert result.evidence_ordinals == (1,)
    assert result.source_citations[0].node_ids == ("paragraph-2",)
    assert "paragraph-2" not in repr(result.source_citations[0])

    rejected: list[str] = []
    for name, candidate in (
        ("unknown-node", payload("paragraph-404")),
        ("missing-maintenance-prompt", payload()),
    ):
        if name == "missing-maintenance-prompt":
            candidate["items"][0]["confirmation"]["required_fields"] = []
        try:
            schema.validate(
                candidate,
                allowed_source_ordinals=allowed_ordinals,
                allowed_source_nodes=allowed_nodes,
            )
        except AIOutputSchemaError:
            rejected.append(name)
        else:
            raise AssertionError(f"unsafe case accepted: {name}")

    print(json.dumps({
        "marker": "AI_04_A07_P02_OUTPUT_V2_PASS",
        "schema": "gap-output.v2@2",
        "accepted_citations": 1,
        "rejected": rejected,
        "real_provider_io": 0,
        "customer_data": 0,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
