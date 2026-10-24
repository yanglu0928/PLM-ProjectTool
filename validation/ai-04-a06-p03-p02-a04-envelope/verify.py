"""Windows proof for deterministic provider-neutral execution envelopes."""

from __future__ import annotations

import hashlib
import json
import socket
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentPlan, AIExecutionContentProjection,
    AIExecutionContentSourceIdentity, AIExecutionContextIdentity,
    AIExecutionPromptIdentity,
)
from plm_assistant.modules.ai.application.execution_envelope import (
    AIExecutionContextPolicyRegistry, AIExecutionEnvelopeBuilder,
    AIExecutionEnvelopeError, AIExecutionTokenEstimatorRegistry,
    Utf8ByteUpperBoundTokenEstimator, require_envelope_for_grant,
)
from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptTaskContent, StrictAIExecutionPromptRenderer,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant, AITaskExecutionInputRef,
)


def main() -> None:
    project = uuid.uuid4()
    input_ref = AITaskExecutionInputRef(
        1, "DOC-02", "document", "DOCUMENT_VERSION",
        uuid.uuid4(), uuid.uuid4(), project,
    )
    system, user = "仅使用授权内容。{context}", "{input}\n参数={parameters}"
    system_hash = hashlib.sha256(system.encode()).hexdigest()
    user_hash = hashlib.sha256(user.encode()).hexdigest()
    grant = AITaskExecutionGrant(
        uuid.uuid4(), project, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        1, 5, "GAP_ANALYSIS", (input_ref,), b"s" * 32,
        "gap-analysis.v1", 1, uuid.uuid4(), 1, system_hash, user_hash,
        "deepseek-chat.v1", "gap-output.v1", 1, "no-retrieval.v1",
        b"t" * 32, uuid.uuid4(), uuid.uuid4(), b"a" * 32,
        "gap.analysis.v1", uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        "deepseek-chat", "PROVIDER_MANAGED", "cn-beijing",
        ("DOCUMENT_TEXT",), b"x" * 32, "minimum.document.text.v1",
        10, 1_000_000, 1_000_000, 3,
        datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    content = json.dumps({
        "nodes": [{"kind": "TEXT_LINE", "node_id": "line-1",
                   "text": "合成需求正文"}],
        "schema_version": "document-minimum-text-v1",
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    source = AIExecutionContentSourceIdentity(
        1, "DOC-02", "document", "DOCUMENT_VERSION",
        input_ref.object_id, input_ref.version_id, project,
        "DOCUMENT_PARSED_TEXT", uuid.uuid4(), uuid.uuid4(),
        "PLAIN_TEXT", "1", "document.parse-result.v1",
        "document.parse.fixed.v1", b"d" * 32, b"e" * 32,
        hashlib.sha256(content).digest(), 500, 1,
    )
    projection = AIExecutionContentProjection(
        source, "document.minimum-text.v1", 1, content)
    prompt_identity = AIExecutionPromptIdentity(
        "gap-analysis.v1", 1, grant.prompt_template_id, 1,
        system_hash, user_hash, "deepseek-chat.v1", "gap-output.v1", 1,
        "strict-placeholders.v1", 1,
    )
    plan = AIExecutionContentPlan(
        uuid.uuid4(), 1, project, "gap.analysis.v1", "GAP_ANALYSIS",
        b"s" * 32, (source,), prompt_identity, b"t" * 32,
        AIExecutionContextIdentity("no-retrieval.v1", "NONE"),
        grant.ai_provider_id, grant.provider_config_version_id,
        grant.ai_model_id, "deepseek-chat", "PROVIDER_MANAGED",
        "cn-beijing", ("DOCUMENT_TEXT",), "minimum.document.text.v1",
        "provider-neutral-json.v1", 1,
        "utf8-byte-upper-bound.v1", 1,
    )
    prompt = AIExecutionPromptTaskContent(
        grant.ai_task_id, project, grant.job_id, grant.requested_by,
        grant.trace_id, "GAP_ANALYSIS", "gap-analysis.v1", 1,
        grant.prompt_template_id, 1, system, user, system_hash, user_hash,
        "deepseek-chat.v1", "gap-output.v1", 1, "no-retrieval.v1",
        {"language": "zh-CN"}, b"t" * 32,
    )
    builder = AIExecutionEnvelopeBuilder(
        renderer=StrictAIExecutionPromptRenderer(),
        context_policies=AIExecutionContextPolicyRegistry(
            frozenset({"no-retrieval.v1"})),
        token_estimators=AIExecutionTokenEstimatorRegistry((
            Utf8ByteUpperBoundTokenEstimator(),)),
    )
    with patch.object(socket, "socket", side_effect=AssertionError("network used")):
        first = builder.build(
            plan=plan, sources=(projection,), prompt_content=prompt)
        second = builder.build(
            plan=plan, sources=(projection,), prompt_content=prompt)
    assert first.canonical_bytes == second.canonical_bytes
    assert first.payload_fingerprint == second.payload_fingerprint
    approved = replace(
        grant, approved_payload_fingerprint=first.payload_fingerprint)
    proof = require_envelope_for_grant(
        approved, plan, first, now=datetime.now(timezone.utc))
    assert proof.payload_bytes == len(first.canonical_bytes)
    assert proof.record_count == 1 and proof.input_tokens == first.input_tokens
    try:
        require_envelope_for_grant(
            replace(approved, max_input_tokens=first.input_tokens - 1),
            plan, first, now=datetime.now(timezone.utc))
    except AIExecutionEnvelopeError:
        pass
    else:
        raise AssertionError("token limit drift accepted")
    rag_plan = replace(
        plan, context=AIExecutionContextIdentity(
            "project-documents.v1", "RAG_CONTEXT", uuid.uuid4(),
            uuid.uuid4(), b"g" * 32, 1, 64))
    rag_prompt = replace(prompt, context_policy_ref="project-documents.v1")
    try:
        builder.build(
            plan=rag_plan, sources=(projection,), prompt_content=rag_prompt)
    except AIExecutionEnvelopeError as error:
        assert error.code == "AI_EXECUTION_CONTEXT_POLICY_UNSUPPORTED"
    else:
        raise AssertionError("unimplemented RAG context accepted")
    print(
        "AI_04_A06_P03_P02_A04_ENVELOPE_PASS: Windows 11/Python 3.13, "
        "canonical provider-neutral UTF-8 envelope stable; source projection hash, "
        "server payload fingerprint, record/byte/token limits bound; only explicit "
        "no-retrieval context accepted; RAG and network I/O rejected"
    )


if __name__ == "__main__":
    main()
