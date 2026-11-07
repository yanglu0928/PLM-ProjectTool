from __future__ import annotations

import uuid
import unittest
from contextlib import contextmanager

from plm_assistant.modules.document.application.generated_artifact_version import (
    GeneratedDocumentVersion, GeneratedVersionError, GeneratedVersionFacts,
    OutputGeneratedDocumentVersionOwner,
)
from plm_assistant.modules.jobs.application.lease import ClaimedJob


class _Transaction:
    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True


class _Jobs:
    def __init__(self, events, claim):
        self.events, self.claim = events, claim

    def check_output_claim(self, transaction, *, job_id, fencing_token, worker_ref):
        self.events.append("job")
        return self.claim


class _Repository:
    def __init__(self, events, facts):
        self.events, self.facts = events, facts

    def lock_request(self, transaction, *, claim, execution_id, publication):
        self.events.append("request")
        return True

    def commit_generated_version(self, transaction, **kwargs):
        self.events.append("commit")
        return self.facts


class _Audit:
    def __init__(self, events, *, fail=False):
        self.events, self.fail = events, fail

    def append(self, transaction, draft):
        self.events.append("audit")
        if self.fail:
            raise RuntimeError("synthetic audit failure")


class GeneratedVersionOwnerTests(unittest.TestCase):
    def setUp(self):
        self.request_id = uuid.uuid4()
        self.snapshot_id = uuid.uuid4()
        self.job_id = uuid.uuid4()
        self.project_id = uuid.uuid4()
        self.document_id = uuid.uuid4()
        self.file_id = uuid.uuid4()
        self.actor_id = uuid.uuid4()
        self.claim = ClaimedJob(
            job_id=self.job_id, job_type="OUTPUT_GENERATE", scope="PROJECT",
            project_id=self.project_id,
            payload_refs={"output_request_id": str(self.request_id),
                          "context_snapshot_id": str(self.snapshot_id)},
            trace_id=str(uuid.uuid4()), fencing_token=3, attempt_no=1,
        )
        execution = uuid.uuid5(self.job_id, "output-generation:3")
        self.version_id = uuid.uuid5(
            execution, "generated-document-version:" + str(self.file_id))
        self.publication = GeneratedDocumentVersion(
            document_id=self.document_id, document_version_id=self.version_id,
            file_object_id=self.file_id, plugin_execution_id=execution,
            sha256=b"x" * 32, size_bytes=8, media_type="image/png",
        )
        self.facts = GeneratedVersionFacts(
            self.request_id, self.project_id, self.document_id, self.version_id,
            self.file_id, execution, uuid.uuid4(), 1, True,
        )

    def _owner(self, *, audit_fail=False):
        self.tx = _Transaction()
        self.events = []

        @contextmanager
        def uow():
            yield self.tx

        return OutputGeneratedDocumentVersionOwner(
            unit_of_work=uow, jobs=_Jobs(self.events, self.claim),
            repository=_Repository(self.events, self.facts),
            audit=_Audit(self.events, fail=audit_fail), system_actor_id=self.actor_id,
        )

    def test_current_fenced_claim_commits_audited_generated_version(self):
        result = self._owner().commit(
            self.claim, worker_ref="synthetic-worker", publication=self.publication)
        self.assertEqual(result, self.facts)
        self.assertEqual(self.events, ["request", "job", "commit", "audit"])
        self.assertTrue(self.tx.committed)

    def test_wrong_execution_identity_fails_before_opening_transaction(self):
        invalid = GeneratedDocumentVersion(
            document_id=self.document_id, document_version_id=self.version_id,
            file_object_id=self.file_id, plugin_execution_id=uuid.uuid4(),
            sha256=b"x" * 32, size_bytes=8, media_type="image/png",
        )
        owner = self._owner()
        with self.assertRaises(GeneratedVersionError):
            owner.commit(self.claim, worker_ref="synthetic-worker", publication=invalid)
        self.assertEqual(self.events, [])

    def test_audit_failure_rolls_back_owner_transaction(self):
        owner = self._owner(audit_fail=True)
        with self.assertRaises(GeneratedVersionError) as raised:
            owner.commit(self.claim, worker_ref="synthetic-worker",
                         publication=self.publication)
        self.assertEqual(raised.exception.code, "SYSTEM_UNAVAILABLE")
        self.assertFalse(self.tx.committed)


if __name__ == "__main__":
    unittest.main()
