from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import replace

from plm_assistant.modules.ai.application.output_schema import (
    GapOutputSchemaV1,
    GapOutputSchemaV2,
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
from plm_assistant.modules.ai.application.task_invocation_begin import (
    BegunAITaskInvocation,
)
from plm_assistant.modules.ai.application.task_invocation_prepare import (
    AIExecutionSourceNodeCatalog,
    PreparedAITaskInvocation,
)
from unit.test_ai_task_provider_send_service import _facts


def _payload():
    return {
        "schema_ref": "gap-output.v1",
        "schema_version": 1,
        "items": [{
            "category": "PENDING_CONFIRMATION",
            "title": "接口边界",
            "summary": "当前资料未固定回写范围。",
            "rationale": "授权输入仅说明存在接口。",
            "recommendation": "由项目负责人确认字段与失败补偿。",
            "source_ordinals": [1],
        }],
    }


def _response(*, content=None, finish="STOP", raw=None):
    if raw is None:
        body = json.dumps({
            "id": "synthetic",
            "choices": [{
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }],
        }, ensure_ascii=False, separators=(",", ":")).encode()
    else:
        body = raw
    return AIProviderResponse(bytearray(body), AIProviderResponseObservation(
        hashlib.sha256(body).digest(), len(body), 10, 5, 7, finish,
    ))


def _payload_v2(node_id="line-1"):
    return {
        "schema_ref": "gap-output.v2",
        "schema_version": 2,
        "items": [{
            "category": "PENDING_CONFIRMATION",
            "title": "接口边界",
            "summary": "当前资料未固定回写范围。",
            "rationale": "授权输入仅说明存在接口。",
            "recommendation": "由项目负责人确认字段与失败补偿。",
            "source_citations": [{"source_ordinal": 1, "node_ids": [node_id]}],
            "confirmation": {
                "required": True,
                "question": "接口需要回写哪些对象和字段？",
                "required_fields": [{
                    "key": "SCOPE", "label": "回写范围",
                    "prompt": "请列出对象、字段和触发时点。",
                    "reason": "用于确认接口边界和失败补偿。",
                    "required": True,
                }],
            },
        }],
    }


class AIProviderSuggestionParserTests(unittest.TestCase):
    def setUp(self):
        _, self.prepared, self.begun, _ = _facts()
        self.parser = AIProviderSuggestionParser(
            schemas=default_ai_output_schema_registry(),
        )

    def parse(self, response):
        return self.parser.parse(
            prepared=self.prepared, begun=self.begun, response=response,
        )

    def test_valid_output_is_canonical_bound_and_not_exposed_in_repr(self):
        payload = _payload()
        response = _response(content=json.dumps(payload, ensure_ascii=False))
        result = self.parse(response)
        expected = json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode()
        self.assertEqual(result.canonical_payload_json, expected)
        self.assertEqual(result.payload_fingerprint, hashlib.sha256(expected).digest())
        self.assertEqual(result.evidence_ordinals, (1,))
        self.assertEqual(result.response_fingerprint,
                         response.observation.response_fingerprint)
        self.assertNotIn("接口边界", repr(result))
        response.close()

    def test_unknown_schema_and_incomplete_response_fail_closed(self):
        alias = default_ai_output_schema_registry().resolve(
            "gap-analysis-output.v1", 1,
        )
        self.assertIsInstance(alias, GapOutputSchemaV1)
        changed_grant = replace(
            self.prepared.grant, output_schema_ref="unknown-output.v1",
        )
        prepared = PreparedAITaskInvocation(
            changed_grant, self.prepared.envelope, self.prepared.payload_plan,
        )
        begun = BegunAITaskInvocation(self.begun.ai_invocation_id, changed_grant)
        response = _response(content=json.dumps(_payload(), ensure_ascii=False))
        with self.assertRaises(AIProviderResponseParseError) as caught:
            self.parser.parse(prepared=prepared, begun=begun, response=response)
        self.assertEqual(caught.exception.code, "AI_OUTPUT_SCHEMA_UNKNOWN")
        response.close()

    def test_v2_requires_exact_nodes_and_structured_confirmation(self):
        alias = default_ai_output_schema_registry().resolve("gap-output.v2", 2)
        self.assertIsInstance(alias, GapOutputSchemaV2)
        changed_grant = replace(
            self.prepared.grant, output_schema_ref="gap-output.v2",
            schema_version=2,
        )
        prepared = PreparedAITaskInvocation(
            changed_grant, self.prepared.envelope, self.prepared.payload_plan,
            (AIExecutionSourceNodeCatalog(1, ("line-1", "line-2")),),
        )
        begun = BegunAITaskInvocation(self.begun.ai_invocation_id, changed_grant)
        response = _response(content=json.dumps(_payload_v2(), ensure_ascii=False))
        result = self.parser.parse(
            prepared=prepared, begun=begun, response=response,
        )
        self.assertEqual(result.evidence_ordinals, (1,))
        self.assertEqual(result.source_citations[0].node_ids, ("line-1",))
        self.assertNotIn("line-1", repr(result))
        response.close()

        invalid = [_payload_v2("missing-node"), _payload_v2()]
        invalid[1]["items"][0]["confirmation"]["required_fields"] = []
        for payload in invalid:
            response = _response(content=json.dumps(payload, ensure_ascii=False))
            with self.assertRaises(AIProviderResponseParseError) as caught:
                self.parser.parse(
                    prepared=prepared, begun=begun, response=response,
                )
            self.assertEqual(caught.exception.code, "AI_OUTPUT_SCHEMA_INVALID")
            response.close()

        response = _response(
            content=json.dumps(_payload(), ensure_ascii=False), finish="LENGTH",
        )
        with self.assertRaises(AIProviderResponseParseError) as caught:
            self.parse(response)
        self.assertEqual(caught.exception.code, "AI_PROVIDER_RESPONSE_INCOMPLETE")
        response.close()

    def test_wrapper_and_payload_ambiguity_or_bounds_are_rejected(self):
        payload = _payload()
        cases = []
        markdown = "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"
        cases.append(_response(content=markdown))
        duplicate = b'{"choices":[{"message":{"content":"{}","content":"{}"}}]}'
        cases.append(_response(raw=duplicate))
        cases.append(_response(content='{"schema_ref":"gap-output.v1",'
                                       '"schema_ref":"gap-output.v1",'
                                       '"schema_version":1,"items":[]}'))
        cases.append(_response(raw=b'{"choices":[{"message":{"content":"{}"}}],'
                                   b'"unsafe":1e9999}'))
        for response in cases:
            with self.subTest(raw=response.observation.response_fingerprint), \
                    self.assertRaises(AIProviderResponseParseError):
                self.parse(response)
            response.close()

    def test_schema_rejects_untrusted_fields_categories_and_source_ordinals(self):
        invalid = []
        value = _payload()
        value["items"][0]["formal_fact"] = True
        invalid.append(value)
        value = _payload()
        value["items"][0]["category"] = "CONFIRMED"
        invalid.append(value)
        value = _payload()
        value["items"][0]["source_ordinals"] = [2]
        invalid.append(value)
        value = _payload()
        value["items"][0]["source_ordinals"] = [1, 1]
        invalid.append(value)
        for payload in invalid:
            response = _response(content=json.dumps(payload, ensure_ascii=False))
            with self.subTest(payload=payload), \
                    self.assertRaises(AIProviderResponseParseError) as caught:
                self.parse(response)
            self.assertEqual(caught.exception.code, "AI_OUTPUT_SCHEMA_INVALID")
            response.close()


if __name__ == "__main__":
    unittest.main()
