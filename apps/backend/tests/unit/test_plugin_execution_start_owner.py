from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.plugin.application.execution_start import (
    PluginExecutionStartError,
    PluginExecutionStartFacts,
    PluginExecutionStartOwner,
    StartPluginExecutionCommand,
)


def fixtures():
    job_id, project_id = uuid.uuid4(), uuid.uuid4()
    request_id, context_id = uuid.uuid4(), uuid.uuid4()
    claim = ClaimedJob(
        job_id=job_id, job_type="OUTPUT_GENERATE", scope="PROJECT",
        project_id=project_id, payload_refs={"output_request_id": str(request_id),
                      "context_snapshot_id": str(context_id)},
        trace_id=str(uuid.uuid4()), fencing_token=7, attempt_no=1,
    )
    facts = PluginExecutionStartFacts(
        plugin_execution_id=uuid.uuid4(), project_id=project_id, job_id=job_id,
        output_request_id=request_id, output_context_snapshot_id=context_id,
        attempt_no=1, execution_state="PENDING", lock_version=0, changed=False,
    )
    return claim, facts


class _Tx:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def commit(self):
        self.committed = True


class _Uow:
    def __init__(self):
        self.tx = _Tx()

    def __call__(self):
        return self.tx

    def __enter__(self):
        return self.tx

    def __exit__(self, *args):
        return False


class _Jobs:
    def __init__(self, current=None, error=False):
        self.current, self.error, self.transactions = current, error, []

    def check_output_claim_in_transaction(self, transaction, **kwargs):
        self.transactions.append(transaction)
        if self.error:
            raise JobLeaseError("STALE_FENCE")
        return self.current


class _Repository:
    def __init__(self, facts, fail_start=False):
        self.facts, self.fail_start = facts, fail_start
        self.transactions, self.authorized, self.events = [], 0, []
        self.start_calls = []

    def lock_execution(self, transaction, **kwargs):
        self.transactions.append(transaction)
        return self.facts

    def authorize_owner_writes(self, transaction):
        self.authorized += 1

    def start_execution(self, transaction, **kwargs):
        self.start_calls.append((transaction, kwargs))
        if self.fail_start:
            raise RuntimeError("synthetic write failure")
        started = replace(self.facts, execution_state="RUNNING",
                          lock_version=self.facts.lock_version + 1, changed=True)
        self.facts = started
        return started

    def append_state_event(self, transaction, **kwargs):
        self.events.append((transaction, kwargs))


class _Audit:
    def __init__(self, fail=False):
        self.events, self.fail = [], fail

    def append(self, transaction, event):
        self.events.append((transaction, event))
        if self.fail:
            raise RuntimeError("synthetic audit failure")
        return uuid.uuid4()


class PluginExecutionStartOwnerTests(unittest.TestCase):
    def create(self, claim, facts, *, repo=None, audit=None, current=None,
               job_error=False):
        uow = _Uow()
        jobs = _Jobs(claim if current is None else current, job_error)
        repository = repo or _Repository(facts)
        audit = audit or _Audit()
        owner = PluginExecutionStartOwner(
            unit_of_work=uow, jobs=jobs, repository=repository, audit=audit,
        )
        return owner, uow, jobs, repository, audit

    def test_pending_transitions_atomically_to_running(self):
        claim, facts = fixtures()
        owner, uow, jobs, repo, audit = self.create(claim, facts)
        result = owner.start(StartPluginExecutionCommand(claim, "worker-1"))
        self.assertTrue(result.changed)
        self.assertEqual(result.execution_state, "RUNNING")
        self.assertEqual(len(repo.start_calls), 1)
        self.assertEqual(len(repo.events), 1)
        self.assertEqual(len(audit.events), 1)
        self.assertIs(repo.start_calls[0][0], uow.tx)
        self.assertIs(repo.events[0][0], uow.tx)
        event = audit.events[0][1]
        self.assertIs(type(event), AuditEventDraft)
        self.assertEqual(event.actor_type, "UNRESOLVED")
        self.assertEqual(event.action, "PLUGIN_EXECUTION_STARTED")
        self.assertTrue(uow.tx.committed)

    def test_running_replay_does_not_duplicate_event_or_audit(self):
        claim, facts = fixtures()
        running = replace(facts, execution_state="RUNNING",
                          lock_version=1, changed=False)
        owner, _uow, _jobs, repo, audit = self.create(claim, running)
        result = owner.start(StartPluginExecutionCommand(claim, "worker-1"))
        self.assertFalse(result.changed)
        self.assertEqual(result.execution_state, "RUNNING")
        self.assertEqual(repo.start_calls, [])
        self.assertEqual(repo.events, [])
        self.assertEqual(audit.events, [])

    def test_stale_fence_fails_before_plugin_row_or_writes(self):
        claim, facts = fixtures()
        owner, _uow, jobs, repo, audit = self.create(claim, facts, job_error=True)
        with self.assertRaises(PluginExecutionStartError):
            owner.start(StartPluginExecutionCommand(claim, "worker-1"))
        self.assertEqual(len(jobs.transactions), 1)
        self.assertEqual(repo.transactions, [])
        self.assertEqual(repo.start_calls, [])
        self.assertEqual(repo.events, [])
        self.assertEqual(audit.events, [])

    def test_execution_output_binding_mismatch_is_rejected(self):
        claim, facts = fixtures()
        mismatched = replace(facts, output_context_snapshot_id=uuid.uuid4())
        owner, _uow, _jobs, repo, audit = self.create(claim, mismatched)
        with self.assertRaises(PluginExecutionStartError):
            owner.start(StartPluginExecutionCommand(claim, "worker-1"))
        self.assertEqual(repo.start_calls, [])
        self.assertEqual(repo.events, [])
        self.assertEqual(audit.events, [])

    def test_terminal_state_is_rejected(self):
        claim, facts = fixtures()
        terminal = replace(facts, execution_state="FAILED")
        owner, _uow, _jobs, repo, audit = self.create(claim, terminal)
        with self.assertRaises(PluginExecutionStartError):
            owner.start(StartPluginExecutionCommand(claim, "worker-1"))
        self.assertEqual(repo.start_calls, [])
        self.assertEqual(repo.events, [])
        self.assertEqual(audit.events, [])

    def test_attempt_two_starts_its_independent_execution(self):
        claim, facts = fixtures()
        retry = replace(claim, attempt_no=2)
        retry_facts = replace(
            facts, plugin_execution_id=uuid.uuid4(), attempt_no=2,
        )
        owner, uow, _jobs, repo, audit = self.create(retry, retry_facts)
        result = owner.start(StartPluginExecutionCommand(retry, "worker-1"))
        self.assertTrue(result.changed)
        self.assertEqual(result.plugin_execution_id, retry_facts.plugin_execution_id)
        self.assertEqual(result.execution_state, "RUNNING")
        self.assertEqual(len(repo.start_calls), 1)
        self.assertEqual(len(repo.events), 1)
        self.assertEqual(len(audit.events), 1)
        self.assertTrue(uow.tx.committed)

    def test_nonpositive_attempt_is_rejected_before_repository_access(self):
        claim, facts = fixtures()
        for attempt_no in (0, -1):
            with self.subTest(attempt_no=attempt_no):
                invalid = replace(claim, attempt_no=attempt_no)
                owner, _uow, _jobs, repo, audit = self.create(invalid, facts)
                with self.assertRaises(PluginExecutionStartError):
                    owner.start(StartPluginExecutionCommand(invalid, "worker-1"))
                self.assertEqual(repo.transactions, [])
                self.assertEqual(repo.start_calls, [])
                self.assertEqual(repo.events, [])
                self.assertEqual(audit.events, [])

    def test_audit_failure_surfaces_fixed_error_and_uow_rolls_back(self):
        claim, facts = fixtures()
        owner, uow, _jobs, repo, audit = self.create(
            claim, facts, audit=_Audit(fail=True),
        )
        with self.assertRaises(PluginExecutionStartError):
            owner.start(StartPluginExecutionCommand(claim, "worker-1"))
        self.assertEqual(len(repo.events), 1)
        self.assertEqual(len(audit.events), 1)
        self.assertFalse(uow.tx.committed)

    def test_claim_contract_rejects_worker_and_noncanonical_trace(self):
        claim, facts = fixtures()
        owner, _uow, _jobs, repo, audit = self.create(claim, facts)
        with self.assertRaises(PluginExecutionStartError):
            owner.start(StartPluginExecutionCommand(claim, "bad worker"))
        malformed = replace(claim, trace_id="not-a-uuid")
        owner, _uow, _jobs, repo, audit = self.create(malformed, facts)
        with self.assertRaises(PluginExecutionStartError):
            owner.start(StartPluginExecutionCommand(malformed, "worker-1"))
        self.assertEqual(repo.start_calls, [])
        self.assertEqual(repo.events, [])
        self.assertEqual(audit.events, [])


if __name__ == "__main__":
    unittest.main()
