from __future__ import annotations

import unittest
import uuid
from contextlib import contextmanager
from dataclasses import replace

from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.output.application.fail_generation import (
    OutputGenerationFailureFacts,
)
from plm_assistant.modules.plugin.application.execution_failure import (
    PluginExecutionFailureError, PluginExecutionFailureFacts,
    PluginExecutionFailureOwner,
)


class _Transaction:
    def __init__(self, state):
        self.state, self.committed = state, False

    def commit(self):
        self.committed = True


class _World:
    def __init__(self):
        self.project, self.job, self.request, self.context = (uuid.uuid4() for _ in range(4))
        self.trace, self.execution, self.requester = (uuid.uuid4() for _ in range(3))
        self.worker = "synthetic.worker"
        self.claim = ClaimedJob(
            self.job, "OUTPUT_GENERATE", "PROJECT", self.project,
            {"output_request_id": str(self.request),
             "context_snapshot_id": str(self.context)},
            str(self.trace), 5, 1,
        )
        self.state = {
            "output": "GENERATING", "job": "RUNNING", "plugin": "RUNNING",
            "output_lock": 1, "plugin_lock": 1, "lease": "ACTIVE",
            "events": [], "output_audit": [], "plugin_audit": [],
        }
        self.fail_plugin_audit = False
        self.fail_output = False

    @contextmanager
    def uow(self):
        tx = _Transaction(self.state)
        saved = {key: list(value) if isinstance(value, list) else value
                 for key, value in self.state.items()}
        try:
            yield tx
        except Exception:
            self.state.clear()
            self.state.update(saved)
            raise

    def fail_in_transaction(self, transaction, claim, *, worker_ref, error_code):
        if (self.fail_output or claim != self.claim or worker_ref != self.worker
                or self.state["output"] != "GENERATING" or error_code not in {
                    "OUTPUT_GENERATION_FAILED", "OUTPUT_PLUGIN_UNAVAILABLE",
                    "OUTPUT_VALIDATION_FAILED",
                }):
            raise RuntimeError("synthetic output failure")
        self.state["job"] = "FAILED"
        self.state["lease"] = "RELEASED"
        self.state["output"] = "FAILED"
        self.state["output_lock"] += 1
        self.state["output_audit"].append(error_code)
        return OutputGenerationFailureFacts(
            self.request, self.project, self.job, self.context, self.requester,
            uuid.uuid5(self.job, "output-generation:" + str(claim.fencing_token)),
            "FAILED", self.state["output_lock"], True,
        )

    def lock_running(self, transaction, *, claim):
        if self.state["plugin"] != "RUNNING" or claim != self.claim:
            raise RuntimeError("synthetic plugin not running")
        return PluginExecutionFailureFacts(
            self.execution, self.project, self.job, self.request, self.context,
            1, self.trace, "RUNNING", self.state["plugin_lock"], False,
        )

    def authorize_owner_writes(self, transaction):
        pass

    def fail_execution(self, transaction, *, claim, plugin_execution_id,
                       expected_lock_version, error_code):
        if (plugin_execution_id != self.execution
                or expected_lock_version != self.state["plugin_lock"]
                or self.state["plugin"] != "RUNNING"):
            raise RuntimeError("synthetic stale plugin row")
        self.state["plugin"] = "FAILED"
        self.state["plugin_lock"] += 1
        return PluginExecutionFailureFacts(
            self.execution, self.project, self.job, self.request, self.context,
            1, self.trace, "FAILED", self.state["plugin_lock"], True,
        )

    def append_failed_event(self, transaction, *, plugin_execution_id, project_id,
                            trace_id, error_code):
        self.state["events"].append((plugin_execution_id, error_code))

    def append(self, transaction, event: AuditEventDraft):
        if self.fail_plugin_audit:
            raise RuntimeError("synthetic plugin audit failure")
        self.state["plugin_audit"].append(event)
        return uuid.uuid4()


class PluginExecutionFailureOwnerTests(unittest.TestCase):
    def setUp(self):
        self.world = _World()
        self.owner = PluginExecutionFailureOwner(
            unit_of_work=self.world.uow, output_failure=self.world,
            repository=self.world, audit=self.world,
        )

    def test_failure_atomically_closes_output_job_and_plugin(self):
        result = self.owner.fail(
            self.world.claim, worker_ref=self.world.worker,
            error_code="OUTPUT_PLUGIN_UNAVAILABLE",
        )
        self.assertEqual((result.execution_state, result.changed), ("FAILED", True))
        self.assertEqual((self.world.state["output"], self.world.state["job"],
                          self.world.state["plugin"], self.world.state["lease"]),
                         ("FAILED", "FAILED", "FAILED", "RELEASED"))
        self.assertEqual(self.world.state["output_audit"],
                         ["OUTPUT_PLUGIN_UNAVAILABLE"])
        self.assertEqual(len(self.world.state["events"]), 1)
        self.assertEqual(len(self.world.state["plugin_audit"]), 1)
        audit = self.world.state["plugin_audit"][0]
        self.assertEqual(type(audit), AuditEventDraft)
        self.assertEqual((audit.actor_type, audit.action, audit.outcome),
                         ("UNRESOLVED", "PLUGIN_EXECUTION_FAILED", "FAILED"))

    def test_plugin_audit_failure_rolls_back_all_three_owners(self):
        self.world.fail_plugin_audit = True
        with self.assertRaises(PluginExecutionFailureError):
            self.owner.fail(self.world.claim, worker_ref=self.world.worker,
                            error_code="OUTPUT_GENERATION_FAILED")
        self.assertEqual((self.world.state["output"], self.world.state["job"],
                          self.world.state["plugin"], self.world.state["lease"]),
                         ("GENERATING", "RUNNING", "RUNNING", "ACTIVE"))
        self.assertEqual(self.world.state["events"], [])
        self.assertEqual(self.world.state["output_audit"], [])
        self.assertEqual(self.world.state["plugin_audit"], [])

    def test_output_failure_stops_before_plugin_write(self):
        self.world.fail_output = True
        with self.assertRaises(PluginExecutionFailureError):
            self.owner.fail(self.world.claim, worker_ref=self.world.worker,
                            error_code="OUTPUT_GENERATION_FAILED")
        self.assertEqual(self.world.state["plugin"], "RUNNING")
        self.assertEqual(self.world.state["events"], [])
        self.assertEqual(self.world.state["plugin_audit"], [])

    def test_bad_error_code_and_worker_are_rejected_before_transaction(self):
        with self.assertRaises(PluginExecutionFailureError):
            self.owner.fail(self.world.claim, worker_ref=self.world.worker,
                            error_code="secret stack trace")
        with self.assertRaises(PluginExecutionFailureError):
            self.owner.fail(self.world.claim, worker_ref="wrong worker",
                            error_code="OUTPUT_GENERATION_FAILED")
        self.assertEqual(self.world.state["output"], "GENERATING")
        self.assertEqual(self.world.state["plugin"], "RUNNING")

    def test_non_running_execution_and_attempt_mismatch_rejected(self):
        self.world.state["plugin"] = "PENDING"
        with self.assertRaises(PluginExecutionFailureError):
            self.owner.fail(self.world.claim, worker_ref=self.world.worker,
                            error_code="OUTPUT_GENERATION_FAILED")
        self.world.state["plugin"] = "RUNNING"
        retry = replace(self.world.claim, attempt_no=2)
        with self.assertRaises(PluginExecutionFailureError):
            self.owner.fail(retry, worker_ref=self.world.worker,
                            error_code="OUTPUT_GENERATION_FAILED")
        self.assertEqual(self.world.state["output"], "GENERATING")
        self.assertEqual(self.world.state["plugin"], "RUNNING")


if __name__ == "__main__":
    unittest.main()
