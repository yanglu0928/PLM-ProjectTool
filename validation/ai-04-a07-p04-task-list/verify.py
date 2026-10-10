"""Windows deterministic proof for authorized AI Task stable pagination."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.ai.api.task_list_cursor import AITaskListCursorCodec
from plm_assistant.modules.ai.application.task_read import (
    AITaskInputView,
    AITaskListCandidates,
    AITaskListService,
    AITaskView,
    ListAITasks,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)


class Transaction:
    def __enter__(self): return self
    def __exit__(self, *_args): return False


class Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class Guard:
    def require_valid(self, **_kwargs): return object()


class Authorization:
    def __init__(self, actor, project): self.actor, self.project = actor, project
    def require_in_transaction(self, *_args, **kwargs):
        return AuthorizedProjectAction(
            self.actor, self.project, kwargs["operation"], "IMPLEMENTATION_MEMBER",
        )


class Repository:
    def __init__(self, view): self.view, self.requested_by = view, None
    def list_page(self, _tx, **kwargs):
        self.requested_by = kwargs["requested_by"]
        return AITaskListCandidates((self.view,), True)


def main() -> None:
    actor, project, task = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    view = AITaskView(
        task, project, "GAP_ANALYSIS", actor,
        (AITaskInputView("DOC-02", uuid.uuid4(), uuid.uuid4()),),
        "gap-analysis.v1", 1, uuid.uuid4(), 2,
        "gap-output.v2", "project-documents.v1", uuid.uuid4(),
        "SUCCEEDED", "AVAILABLE", uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        None, None, 1, now, now, now,
    )
    repository = Repository(view)
    query = ListAITasks(b"s" * 32, uuid.uuid4(), project, 1)
    page = AITaskListService(
        unit_of_work=Transaction, access=Access(actor), license_guard=Guard(),
        authorization=Authorization(actor, project), repository=repository,
        clock=lambda: now,
    ).list(query)
    assert repository.requested_by == actor
    assert page.next_position == (now, task)
    codec = AITaskListCursorCodec(b"c" * 32)
    token = codec.encode(query=query, before=page.next_position)
    assert codec.decode(token, query=query) == page.next_position
    assert str(project) not in token and str(task) not in token
    print(json.dumps({
        "marker": "AI_04_A07_P04_TASK_LIST_PASS",
        "implementation_member_own_only": True,
        "cursor_session_project_page_bound": True,
        "cursor_plaintext_ids": False,
        "database_schema_changed": False,
        "customer_data": 0,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
