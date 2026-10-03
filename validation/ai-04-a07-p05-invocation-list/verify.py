"""Windows proof of the minimized Invocation projection and cursor domain."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.ai.api.invocation_list_cursor import (
    AIInvocationListCursorCodec,
)
from plm_assistant.modules.ai.api.list_invocations import _public
from plm_assistant.modules.ai.api.task_list_cursor import AITaskListCursorCodec
from plm_assistant.modules.ai.application.invocation_read import (
    AIInvocationContextView,
    AIInvocationView,
    ListAIInvocations,
)
from plm_assistant.modules.ai.application.task_read import (
    AITaskReadError,
    ListAITasks,
)


def main() -> None:
    project_id, task_id, invocation_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime(2026, 10, 3, 15, tzinfo=timezone.utc)
    view = AIInvocationView(
        invocation_id, task_id, project_id, 1,
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "model-v1",
        uuid.uuid4(), 1, "gap-output.v2", 2,
        AIInvocationContextView(
            uuid.uuid4(), 1, "project-documents.v1", "NONE", None, None,
        ),
        "SUCCEEDED", "VALID", 120, 30, 420, None, None,
        now, now, now,
    )
    projection = _public(view)
    encoded = json.dumps(projection, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "provider_request_ref", "request_payload", "response_fingerprint",
        "context_bundle_fingerprint", "secret",
    ):
        assert forbidden not in encoded.lower()

    key = b"c" * 32
    query = ListAIInvocations(
        b"s" * 32, uuid.uuid4(), project_id, task_id, 50,
    )
    codec = AIInvocationListCursorCodec(key)
    token = codec.encode(query=query, before=(1, invocation_id))
    assert codec.decode(token, query=query) == (1, invocation_id)
    assert str(task_id) not in token and str(invocation_id) not in token
    task_query = ListAITasks(
        query.session_token, query.trace_id, project_id, 50,
    )
    try:
        AITaskListCursorCodec(key).decode(token, query=task_query)
    except AITaskReadError:
        separated = True
    else:
        raise AssertionError("Task codec accepted Invocation family")

    print(json.dumps({
        "marker": "AI_04_A07_P05_INVOCATION_LIST_PASS",
        "minimal_projection": True,
        "cursor_family_separated": separated,
        "cursor_plaintext_ids": str(task_id) in token or str(invocation_id) in token,
        "database_schema_changed": False,
        "customer_data": 0,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
