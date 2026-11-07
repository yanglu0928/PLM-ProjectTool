from __future__ import annotations

import unittest
import uuid
from contextlib import contextmanager
from dataclasses import replace

from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.output.application.job_admission import (
    OutputExecutionAdmission, OutputJobAdmissionError,
)
from plm_assistant.modules.plugin.application.execution_admission import (
    AdmitPluginExecutionCommand,
    PluginExecutionAdmissionError,
    PluginExecutionAdmissionOwner,
    PluginExecutionAdmissionSnapshot,
    PluginExecutionTarget,
)

def fixtures():
    job_id, project_id, request_id, snapshot_id = (uuid.uuid4() for _ in range(4))
    installation_id, package_id = uuid.uuid4(), uuid.uuid4()
    trace_id = uuid.uuid4()
    claim = ClaimedJob(
        job_id=job_id, job_type="OUTPUT_GENERATE", scope="PROJECT",
        project_id=project_id,
        payload_refs={"output_request_id": str(request_id),
                      "context_snapshot_id": str(snapshot_id)},
        trace_id=str(trace_id), fencing_token=7, attempt_no=1,
    )
    admission = OutputExecutionAdmission(
        output_request_id=request_id, project_id=project_id, job_id=job_id,
        context_snapshot_id=snapshot_id, output_type="DOCX",
        template_version_ref=uuid.uuid4(), source_version_refs=(uuid.uuid4(),),
        output_policy_ref="POLICY-1", plugin_operation="doc.generate",
        input_fingerprint=b"i" * 32, context_fingerprint=b"c" * 32,
    )
    target = PluginExecutionTarget(
        plugin_installation_id=installation_id, plugin_package_id=package_id,
        plugin_id_normalized="demo.plugin", operation_id="doc.generate",
    )
    return claim, admission, target

class _Uow:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.transaction = object()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.rollbacks += 1
        return False

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

class _Jobs:
    def __init__(self, current=None, error=None):
        self.current, self.error, self.transactions = current, error, []

    def check_output_claim_in_transaction(self, transaction, **kwargs):
        self.transactions.append(transaction)
        if self.error:
            raise self.error
        return self.current

class _Output:
    def __init__(self, value=None, error=None):
        self.value, self.error, self.transactions = value, error, []

    def admit_in_transaction(self, transaction, claim):
        self.transactions.append((transaction, claim))
        if self.error:
            raise self.error
        return self.value

class _Targets:
    def __init__(self, value):
        self.value, self.transactions = value, []

    def get_execution_target(self, transaction, *, operation_id):
        self.transactions.append((transaction, operation_id))
        return self.value

class _Repository:
    def __init__(self):
        self.existing = None
        self.writes = []
        self.events = []
        self.authorized = 0

    def find_by_job(self, transaction, *, job_id):
        return self.existing

    def authorize_owner_writes(self, transaction):
        self.authorized += 1

    def create_pending(self, transaction, **kwargs):
        command, admission, target = kwargs["command"], kwargs["admission"], kwargs["target"]
        claim = command.claim
        row = PluginExecutionAdmissionSnapshot(
            plugin_execution_id=kwargs["plugin_execution_id"],
            project_id=admission.project_id,
            output_request_id=admission.output_request_id,
            output_context_snapshot_id=admission.context_snapshot_id,
            plugin_installation_id=target.plugin_installation_id,
            plugin_package_id=target.plugin_package_id,
            plugin_id_normalized=target.plugin_id_normalized,
            operation_id=target.operation_id,
            context_fingerprint=admission.context_fingerprint,
            job_id=claim.job_id, attempt_no=claim.attempt_no,
            execution_state="PENDING",
        )
        self.existing = row
        self.writes.append(kwargs)
        return row

    def append_pending_event(self, transaction, **kwargs):
        self.events.append((transaction, kwargs))

class _Audit:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail

    def append(self, transaction, event):
        self.events.append((transaction, event))
        if self.fail:
            raise RuntimeError("synthetic audit failure")
        return uuid.uuid4()

class PluginExecutionAdmissionOwnerTests(unittest.TestCase):
    def create(self, claim, admission, target, *, repo=None, audit=None,
               current=None, job_error=None, output_error=None):
        uow = _Uow()
        jobs = _Jobs(current if current is not None else claim, job_error)
        output = _Output(admission, output_error)
        targets = _Targets(target)
        repository = repo or _Repository()
        audit = audit or _Audit()
        owner = PluginExecutionAdmissionOwner(
            unit_of_work=lambda: uow, jobs=jobs, output_admission=output,
            targets=targets, repository=repository, audit=audit,
        )
        return owner, uow, jobs, output, targets, repository, audit

    def test_admission_atomically_creates_pending_root_event_and_audit(self):
        claim, admission, target = fixtures()
        owner, uow, jobs, output, targets, repo, audit = self.create(
            claim, admission, target,
        )
        result = owner.admit(AdmitPluginExecutionCommand(claim, "worker-1"))
        tx = uow

        self.assertTrue(result.created)
        self.assertEqual(result.execution_state, "PENDING")
        self.assertEqual(len(repo.writes), 1)
        self.assertEqual(len(repo.events), 1)
        self.assertEqual(len(audit.events), 1)
        self.assertEqual(repo.authorized, 1)
        self.assertIs(jobs.transactions[0], tx)
        self.assertIs(output.transactions[0][0], tx)
        self.assertIs(targets.transactions[0][0], tx)
        event = audit.events[0][1]
        self.assertIs(type(event), AuditEventDraft)
        self.assertEqual(event.actor_type, "UNRESOLVED")
        self.assertEqual(uow.commits, 1)

    def test_exact_job_replay_is_idempotent(self):
        claim, admission, target = fixtures()
        repo = _Repository()
        owner, uow, *_rest = self.create(claim, admission, target, repo=repo)
        first = owner.admit(AdmitPluginExecutionCommand(claim, "worker-1"))
        replay = owner.admit(AdmitPluginExecutionCommand(claim, "worker-1"))
        self.assertTrue(first.created)
        self.assertFalse(replay.created)
        self.assertEqual(first.plugin_execution_id, replay.plugin_execution_id)
        self.assertEqual(len(repo.writes), 1)
        self.assertEqual(len(repo.events), 1)

    def test_retry_attempt_is_rejected_until_predecessor_proof_exists(self):
        claim, admission, target = fixtures()
        owner, _uow, jobs, _output, targets, repo, audit = self.create(
            replace(claim, attempt_no=2), admission, target,
        )
        with self.assertRaises(PluginExecutionAdmissionError):
            owner.admit(AdmitPluginExecutionCommand(
                replace(claim, attempt_no=2), "worker-1",
            ))
        self.assertEqual(jobs.transactions, [])
        self.assertEqual(targets.transactions, [])
        self.assertEqual(repo.writes, [])
        self.assertEqual(audit.events, [])

    def test_stale_claim_and_output_rejection_are_fail_closed(self):
        claim, admission, target = fixtures()
        other_claim = replace(claim, fencing_token=8)
        owner, _, _, output, targets, repo, audit = self.create(
            claim, admission, target, current=other_claim,
        )
        with self.assertRaises(PluginExecutionAdmissionError):
            owner.admit(AdmitPluginExecutionCommand(claim, "worker-1"))
        self.assertEqual(output.transactions, [])
        self.assertEqual(targets.transactions, [])
        self.assertEqual(repo.writes, [])
        self.assertEqual(audit.events, [])

        owner, _, _, _, targets, repo, audit = self.create(
            claim, admission, target, output_error=OutputJobAdmissionError(),
        )
        with self.assertRaises(PluginExecutionAdmissionError):
            owner.admit(AdmitPluginExecutionCommand(claim, "worker-1"))
        self.assertEqual(targets.transactions, [])
        self.assertEqual(repo.writes, [])
        self.assertEqual(audit.events, [])

    def test_audit_failure_rolls_back_owner_transaction(self):
        claim, admission, target = fixtures()
        audit = _Audit(fail=True)
        owner, uow, _jobs, _output, _targets, repo, _audit = self.create(
            claim, admission, target, audit=audit,
        )
        with self.assertRaises(PluginExecutionAdmissionError):
            owner.admit(AdmitPluginExecutionCommand(claim, "worker-1"))
        self.assertEqual(uow.rollbacks, 1)
        self.assertEqual(len(repo.writes), 1)
        self.assertEqual(len(repo.events), 1)

    def test_non_output_job_and_malformed_worker_are_rejected_before_uow(self):
        claim, admission, target = fixtures()
        owner, uow, jobs, _output, targets, repo, audit = self.create(
            replace(claim, job_type="AUDIT_EXPORT"), admission, target,
        )
        with self.assertRaises(PluginExecutionAdmissionError):
            owner.admit(AdmitPluginExecutionCommand(
                replace(claim, job_type="AUDIT_EXPORT"), "worker-1",
            ))
        self.assertEqual(jobs.transactions, [])
        self.assertEqual(targets.transactions, [])
        self.assertEqual(repo.writes, [])
        self.assertEqual(audit.events, [])

        with self.assertRaises(PluginExecutionAdmissionError):
            owner.admit(AdmitPluginExecutionCommand(claim, "bad worker"))
        self.assertEqual(uow.commits, 0)

if __name__ == "__main__":
    unittest.main()
