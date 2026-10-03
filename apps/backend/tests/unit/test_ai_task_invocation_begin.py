from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant, AITaskExecutionInputRef,
)
from plm_assistant.modules.ai.application.task_invocation_begin import (
    AITaskInvocationBeginError, AITaskInvocationBeginService,
)


class _Transaction:
    def __init__(self, owner):
        self.owner = owner

    def __enter__(self):
        return self

    def commit(self):
        self.owner.commit_called = True

    def __exit__(self, kind, *_):
        self.owner.committed = kind is None and self.owner.commit_called
        return False


class _Uow:
    def __init__(self):
        self.committed = False
        self.commit_called = False

    def __call__(self):
        return _Transaction(self)


class _Grants:
    def __init__(self, grant, fail_after=False):
        self.grant, self.fail_after = grant, fail_after
        self.transactions = []
        self.after_commit = 0

    def issue_in(self, transaction, **kwargs):
        del kwargs
        self.transactions.append(transaction)
        return self.grant

    def require_usable(self, grant):
        self.after_commit += 1
        if self.fail_after:
            raise RuntimeError("license changed")
        self.assert_grant = grant


class _Repository:
    def __init__(self, invocation_id):
        self.invocation_id = invocation_id
        self.transactions = []

    def begin(self, transaction, **kwargs):
        del kwargs
        self.transactions.append(transaction)
        return self.invocation_id


def grant(now: datetime) -> AITaskExecutionGrant:
    project = uuid.uuid4()
    return AITaskExecutionGrant(
        uuid.uuid4(), project, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        1, 1, "GAP_ANALYSIS", (AITaskExecutionInputRef(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            uuid.uuid4(), uuid.uuid4(), project,
        ),), b"s" * 32, "gap-analysis.v1", 1, uuid.uuid4(), 1,
        "a" * 64, "b" * 64, "provider.v1", "gap-output.v1", 1,
        "no-retrieval.v1", b"t" * 32, uuid.uuid4(), uuid.uuid4(),
        b"a" * 32, "project-gap-analysis.v1", uuid.uuid4(), uuid.uuid4(),
        uuid.uuid4(), "chat", "PROVIDER_MANAGED", "cn-beijing",
        ("DOCUMENT_TEXT",), b"p" * 32, "minimum.document.text.v1",
        1, 65536, 4096, 3, now + timedelta(minutes=10), uuid.uuid4(),
    )


class AITaskInvocationBeginTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
        self.grant = grant(self.now)

    def test_grant_and_persist_share_transaction_then_recheck(self):
        uow, grants, repository = _Uow(), _Grants(self.grant), _Repository(uuid.uuid4())
        result = AITaskInvocationBeginService(
            unit_of_work=uow, grants=grants, repository=repository,
        ).begin(job_id=self.grant.job_id, fencing_token=1,
                worker_ref="worker-a", now=self.now)
        self.assertTrue(uow.committed)
        self.assertIs(grants.transactions[0], repository.transactions[0])
        self.assertEqual(result.grant, self.grant)
        self.assertEqual(grants.after_commit, 1)

    def test_invalid_result_or_post_commit_guard_fails_closed(self):
        for repository, grants in (
            (_Repository(uuid.UUID(int=0)), _Grants(self.grant)),
            (_Repository(uuid.uuid4()), _Grants(self.grant, fail_after=True)),
        ):
            with self.subTest(repository=repository, grants=grants), \
                    self.assertRaises(AITaskInvocationBeginError):
                AITaskInvocationBeginService(
                    unit_of_work=_Uow(), grants=grants, repository=repository,
                ).begin(job_id=self.grant.job_id, fencing_token=1,
                        worker_ref="worker-a", now=self.now)


if __name__ == "__main__":
    unittest.main()
