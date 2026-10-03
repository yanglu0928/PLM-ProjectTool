from __future__ import annotations

import json
import unittest
import uuid
from unittest.mock import patch

from plm_assistant.modules.ai.application.complete_provider_success import (
    AITaskProviderSuccessError,
    AITaskProviderSuccessService,
)
from plm_assistant.modules.ai.application.output_schema import (
    default_ai_output_schema_registry,
)
from plm_assistant.modules.ai.application.provider_response_parser import (
    AIProviderSuggestionParser,
)
from plm_assistant.modules.ai.application.publish_suggestion_success import (
    AISuggestionEvidence,
    AITaskSuggestionPublicationError,
    AITaskSuggestionSuccessPublisher,
    PublishedAITaskSuggestion,
)
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from unit.test_ai_provider_response_parser import _payload, _response
from unit.test_ai_task_provider_send_service import _facts


class _Transaction:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.committed = True


class _Uow:
    def __init__(self):
        self.transactions = []

    def __call__(self):
        transaction = _Transaction()
        self.transactions.append(transaction)
        return transaction


class _Actor:
    def __init__(self):
        self.value = uuid.uuid4()

    def assert_current(self):
        return self.value


class _Jobs:
    def __init__(self, grant, *, fail=False):
        self.grant, self.fail = grant, fail
        self.calls = []

    def finish(self, transaction, **values):
        self.calls.append((transaction, values))
        if self.fail:
            raise JobLeaseError("STALE_LEASE")
        grant = self.grant
        return ClaimedJob(
            grant.job_id, "AI_TASK_EXECUTE", "PROJECT", grant.project_id,
            {
                "ai_task_id": str(grant.ai_task_id),
                "egress_authorization_ref": str(grant.authorization_ref),
                "input_fingerprint": grant.source_refs_fingerprint.hex(),
            },
            str(grant.trace_id), grant.fencing_token, grant.attempt_no,
        )


class _Plans:
    def get(self, *_args, **_kwargs):
        return object()


class _Store:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def publish(self, transaction, **values):
        self.calls.append((transaction, values))
        return self.result


class _Audit:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.events = []

    def append(self, transaction, event):
        self.events.append((transaction, event))
        if self.fail:
            raise RuntimeError("synthetic audit failure")
        return uuid.uuid4()


class _Publisher:
    def __init__(self, result=None, failure=None):
        self.result, self.failure = result, failure
        self.calls = []

    def publish(self, **values):
        self.calls.append(values)
        if self.failure:
            raise self.failure
        return self.result


class AITaskSuggestionSuccessTests(unittest.TestCase):
    def setUp(self):
        self.now, self.prepared, self.begun, _ = _facts()
        self.parser = AIProviderSuggestionParser(
            schemas=default_ai_output_schema_registry(),
        )
        response = _response(content=json.dumps(
            _payload(), ensure_ascii=False,
        ))
        try:
            self.parsed = self.parser.parse(
                prepared=self.prepared, begun=self.begun, response=response,
            )
        finally:
            response.close()
        self.result = PublishedAITaskSuggestion(uuid.uuid4(), self.now)
        source = self.prepared.grant.input_refs[0]
        self.evidence = AISuggestionEvidence(
            1, source.owner_module, source.object_type,
            source.object_id, source.version_id, b"e" * 32,
        )

    def test_atomic_publisher_finishes_resolves_stores_audits_and_commits(self):
        uow = _Uow()
        jobs = _Jobs(self.prepared.grant)
        store = _Store(self.result)
        audit = _Audit()
        actor = _Actor()
        publisher = AITaskSuggestionSuccessPublisher(
            unit_of_work=uow, plans=_Plans(), store=store,
            jobs=jobs, audit=audit, system_actor=actor,
        )
        with patch.object(
            AITaskSuggestionSuccessPublisher, "_resolve_evidence",
            return_value=(self.evidence,),
        ):
            result = publisher.publish(
                parsed=self.parsed, prepared=self.prepared,
                begun=self.begun, worker_ref="worker-a",
            )
        self.assertEqual(result, self.result)
        self.assertTrue(uow.transactions[0].committed)
        self.assertEqual(len(jobs.calls), 1)
        self.assertEqual(store.calls[0][1]["evidence"], (self.evidence,))
        event = audit.events[0][1]
        self.assertEqual(event.action, "AI_TASK_SUGGESTION_AVAILABLE")
        self.assertEqual(event.target_version_id, self.result.suggestion_payload_id)

    def test_job_or_audit_failure_never_commits(self):
        for jobs, audit, expected in (
            (_Jobs(self.prepared.grant, fail=True), _Audit(),
             "AI_TASK_JOB_LEASE_LOST"),
            (_Jobs(self.prepared.grant), _Audit(fail=True),
             "AI_TASK_RESULT_NOT_PUBLISHED"),
        ):
            uow = _Uow()
            publisher = AITaskSuggestionSuccessPublisher(
                unit_of_work=uow, plans=_Plans(), store=_Store(self.result),
                jobs=jobs, audit=audit, system_actor=_Actor(),
            )
            with patch.object(
                AITaskSuggestionSuccessPublisher, "_resolve_evidence",
                return_value=(self.evidence,),
            ), self.subTest(expected=expected), self.assertRaises(
                    AITaskSuggestionPublicationError) as caught:
                publisher.publish(
                    parsed=self.parsed, prepared=self.prepared,
                    begun=self.begun, worker_ref="worker-a",
                )
            self.assertEqual(caught.exception.code, expected)
            self.assertFalse(uow.transactions[0].committed)

    def test_success_service_always_closes_response(self):
        response = _response(content=json.dumps(
            _payload(), ensure_ascii=False,
        ))
        publisher = _Publisher(result=self.result)
        service = AITaskProviderSuccessService(
            parser=self.parser, publisher=publisher,
        )
        self.assertEqual(service.complete(
            prepared=self.prepared, begun=self.begun, response=response,
            worker_ref="worker-a",
        ), self.result)
        with self.assertRaises(Exception):
            response.view()

        response = _response(content=json.dumps(
            _payload(), ensure_ascii=False,
        ))
        service = AITaskProviderSuccessService(
            parser=self.parser,
            publisher=_Publisher(failure=AITaskSuggestionPublicationError()),
        )
        with self.assertRaises(AITaskProviderSuccessError):
            service.complete(
                prepared=self.prepared, begun=self.begun, response=response,
                worker_ref="worker-a",
            )
        with self.assertRaises(Exception):
            response.view()


if __name__ == "__main__":
    unittest.main()
