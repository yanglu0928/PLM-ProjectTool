"""Windows 11 proof for trusted Output Schema and bounded response parsing."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from plm_assistant.modules.ai.application.output_schema import (
    default_ai_output_schema_registry,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderResponse,
    AIProviderResponseObservation,
)
from plm_assistant.modules.ai.application.provider_response_parser import (
    AIProviderResponseParseError,
    AIProviderSuggestionParser,
)


def load_helper(directory: str, name: str):
    path = Path(__file__).resolve().parents[1] / directory / "verify.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def response(content: str, *, finish: str = "STOP") -> AIProviderResponse:
    body = json.dumps({
        "id": "synthetic-no-network",
        "choices": [{
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
    }, ensure_ascii=False, separators=(",", ":")).encode()
    return AIProviderResponse(bytearray(body), AIProviderResponseObservation(
        hashlib.sha256(body).digest(), len(body), 100, 50, 9, finish,
    ))


def validate(context: dict[str, object]) -> None:
    prepared = context["prepared_invocation"]
    begun = context["begun_invocation"]
    parser = AIProviderSuggestionParser(
        schemas=default_ai_output_schema_registry(),
    )
    payload = {
        "schema_ref": "gap-output.v1",
        "schema_version": 1,
        "items": [{
            "category": "PENDING_CONFIRMATION",
            "title": "接口边界",
            "summary": "当前授权资料未固定回写范围。",
            "rationale": "输入资料只证明接口需求存在。",
            "recommendation": "确认字段、触发条件与失败补偿。",
            "source_ordinals": [1],
        }],
    }
    valid = response(json.dumps(payload, ensure_ascii=False))
    try:
        result = parser.parse(
            prepared=prepared, begun=begun, response=valid,
        )
        assert result.evidence_ordinals == (1,)
        assert result.output_schema_ref == "gap-output.v1"
        assert result.schema_version == 1
        assert json.loads(result.canonical_payload_json) == payload
    finally:
        valid.close()

    invalid_payload = {**payload, "formal_fact": True}
    invalid = response(json.dumps(invalid_payload, ensure_ascii=False))
    try:
        try:
            parser.parse(prepared=prepared, begun=begun, response=invalid)
        except AIProviderResponseParseError as error:
            assert error.code == "AI_OUTPUT_SCHEMA_INVALID"
        else:
            raise AssertionError("untrusted output field accepted")
    finally:
        invalid.close()

    print(
        "AI_04_A06_P07_P04_OUTPUT_SCHEMA_PARSER_PASS: Windows11 validated the "
        "trusted gap-output.v1@1 registry, strict OpenAI-compatible wrapper and "
        "inner JSON parsing, canonical payload fingerprint and authorized source "
        "ordinal; unknown formal-fact fields were rejected, response buffers were "
        "zeroized, and no real Provider network I/O occurred"
    )


def main() -> None:
    helper = load_helper(
        "ai-04-a06-p06-p03-pre-send-owner", "p07p04_pre_send_helper",
    )
    helper.main(after_authorized=validate)


if __name__ == "__main__":
    main()
