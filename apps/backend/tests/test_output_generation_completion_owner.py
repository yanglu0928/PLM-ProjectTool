from __future__ import annotations

import unittest
import uuid
from contextlib import contextmanager

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.output.application.complete_generation import (
    OutputArtifactPublication, OutputGenerationCompletionError,
    OutputGenerationCompletionFacts, OutputGenerationCompletionOwner,
    OutputValidationEvidence,
)


class FakeTransaction:
    def __init__(self, state):
        self.state = state
    def commit(self):
        self.state["committed"] = True


class FakeWorld:
    def __init__(self):
        self.request_id, self.project_id, self.job_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.snapshot_id, self.requester_id, self.system_id, self.trace_id = (uuid.uuid4() for _ in range(4))
        self.execution_id = uuid.uuid5(self.job_id, "output-generation:7")
        self.claim = ClaimedJob(
            self.job_id, "OUTPUT_GENERATE", "PROJECT", self.project_id,
            {"output_request_id":str(self.request_id),"context_snapshot_id":str(self.snapshot_id)},
            str(self.trace_id), 7, 2,
        )
        self.state = {"request":"GENERATING","artifact":"MISSING","job":"RUNNING",
                      "lease":"ACTIVE","lock":1,"audit":[],"committed":False}
        self.fail_audit = False
        self.calls = 0
        self.publication = OutputArtifactPublication(
            uuid.uuid4(), self.execution_id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            bytes.fromhex("ab"*32), 17,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            tuple(OutputValidationEvidence(code,"PASSED",bytes.fromhex("cd"*32) if code!="HASH_CHECK" else bytes.fromhex("ab"*32))
                  for code in ("FORMAT_CHECK","STRUCTURE_CHECK","HASH_CHECK","CONTENT_CHECK")),
        )

    @contextmanager
    def unit_of_work(self):
        saved = {**self.state,"audit":list(self.state["audit"])}
        tx = FakeTransaction(self.state)
        try:
            yield tx
        except Exception:
            self.state.clear()
            self.state.update(saved)
            raise

    def facts(self, *, changed):
        return OutputGenerationCompletionFacts(
            self.publication.artifact_id if self.state["artifact"]=="AVAILABLE" else None,
            self.request_id,self.project_id,self.job_id,self.snapshot_id,self.requester_id,
            self.execution_id,"DOCX",self.state["request"],self.state["artifact"],
            self.state["lock"],changed,
        )

    def lock_candidate(self, transaction, *, claim, execution_id):
        if (claim.job_id!=self.job_id or execution_id!=self.execution_id
                or self.state["request"] not in {"GENERATING","SUCCEEDED"}):
            raise OutputGenerationCompletionError()
        return self.facts(changed=False)

    def verify_completed_generation(self, transaction, *, claim, execution_id, publication):
        if (self.state["request"]!="SUCCEEDED" or self.state["artifact"]!="AVAILABLE"
                or publication!=self.publication or execution_id!=self.execution_id):
            raise OutputGenerationCompletionError()
        return self.facts(changed=False)

    def complete_generation(self, transaction, *, claim, execution_id,
                            expected_lock_version, publication):
        if (self.state["lock"]!=expected_lock_version or publication!=self.publication
                or execution_id!=self.execution_id):
            raise OutputGenerationCompletionError()
        self.state["request"]="SUCCEEDED"
        self.state["artifact"]="AVAILABLE"
        self.state["lock"]+=1
        self.calls+=1
        return self.facts(changed=True)

    def check_output_claim(self, transaction, *, job_id, fencing_token, worker_ref):
        if (job_id!=self.job_id or fencing_token!=7 or worker_ref!="worker-1"
                or self.state["lease"]!="ACTIVE"):
            raise JobLeaseError("STALE_LEASE")
        return self.claim

    def check_output_success(self, transaction, *, job_id, fencing_token, worker_ref):
        if (job_id!=self.job_id or fencing_token!=7 or worker_ref!="worker-1"
                or self.state["job"]!="SUCCEEDED" or self.state["lease"]!="RELEASED"):
            raise JobLeaseError("STALE_LEASE")
        return self.claim

    def finish(self, transaction, *, job_id, fencing_token, worker_ref):
        if (job_id!=self.job_id or fencing_token!=7 or worker_ref!="worker-1"
                or self.state["lease"]!="ACTIVE"):
            raise JobLeaseError("STALE_LEASE")
        self.state["job"]="SUCCEEDED"
        self.state["lease"]="RELEASED"
        return self.claim


class FakeAudit:
    def __init__(self, world):
        self.world=world
    def append(self, transaction, event: AuditEventDraft):
        if self.world.fail_audit:
            raise RuntimeError("synthetic audit failure")
        self.world.state["audit"].append(event)
        return uuid.uuid4()


class OutputGenerationCompletionOwnerTests(unittest.TestCase):
    def setUp(self):
        self.world=FakeWorld()
        self.owner=OutputGenerationCompletionOwner(
            unit_of_work=self.world.unit_of_work,jobs=self.world,repository=self.world,
            audit=FakeAudit(self.world),system_actor_id=self.world.system_id,
        )

    def test_complete_is_atomic_and_records_system_audit(self):
        facts=self.owner.complete(self.world.claim,worker_ref="worker-1",
                                  publication=self.world.publication)
        self.assertEqual((facts.request_state,facts.artifact_state,facts.changed),
                         ("SUCCEEDED","AVAILABLE",True))
        self.assertEqual((self.world.state["job"],self.world.state["lease"]),
                         ("SUCCEEDED","RELEASED"))
        event=self.world.state["audit"][0]
        self.assertEqual((event.action,event.outcome,event.before_state,event.after_state),
                         ("OUTPUT_GENERATION_SUCCEEDED","SUCCESS","GENERATING","SUCCEEDED"))
        self.assertEqual((event.actor_id,event.original_actor_id),
                         (self.world.system_id,self.world.requester_id))

    def test_exact_success_replay_returns_original_facts_without_writes(self):
        first=self.owner.complete(self.world.claim,worker_ref="worker-1",
                                  publication=self.world.publication)
        before=(self.world.state["request"],self.world.state["artifact"],
                self.world.state["job"],self.world.state["lease"],
                len(self.world.state["audit"]),self.world.calls)
        replay=self.owner.complete(self.world.claim,worker_ref="worker-1",
                                   publication=self.world.publication)
        after=(self.world.state["request"],self.world.state["artifact"],
               self.world.state["job"],self.world.state["lease"],
               len(self.world.state["audit"]),self.world.calls)
        self.assertEqual(
            (replay.artifact_id,replay.output_request_id,replay.project_id,replay.job_id,
             replay.context_snapshot_id,replay.requested_by,replay.execution_id,
             replay.output_type,replay.request_state,replay.artifact_state,replay.lock_version),
            (first.artifact_id,first.output_request_id,first.project_id,first.job_id,
             first.context_snapshot_id,first.requested_by,first.execution_id,
             first.output_type,first.request_state,first.artifact_state,first.lock_version),
        )
        self.assertFalse(replay.changed)
        self.assertEqual(after,before)

    def test_audit_failure_rolls_back_all_four_owners(self):
        self.world.fail_audit=True
        with self.assertRaises(OutputGenerationCompletionError):
            self.owner.complete(self.world.claim,worker_ref="worker-1",
                                publication=self.world.publication)
        self.assertEqual((self.world.state["request"],self.world.state["artifact"],
                          self.world.state["job"],self.world.state["lease"]),
                         ("GENERATING","MISSING","RUNNING","ACTIVE"))
        self.assertFalse(self.world.state["committed"])

    def test_stale_fencing_token_is_rejected(self):
        stale=ClaimedJob(self.world.claim.job_id,self.world.claim.job_type,
            self.world.claim.scope,self.world.claim.project_id,self.world.claim.payload_refs,
            self.world.claim.trace_id,6,self.world.claim.attempt_no)
        with self.assertRaises(OutputGenerationCompletionError):
            self.owner.complete(stale,worker_ref="worker-1",publication=self.world.publication)
        self.assertEqual(self.world.calls,0)

    def test_wrong_worker_is_rejected_without_changes(self):
        with self.assertRaises(OutputGenerationCompletionError):
            self.owner.complete(self.world.claim,worker_ref="worker-2",
                                publication=self.world.publication)
        self.assertEqual((self.world.state["request"],self.world.state["job"]),
                         ("GENERATING","RUNNING"))

    def test_non_output_job_is_rejected(self):
        wrong=ClaimedJob(self.world.claim.job_id,"DOCUMENT_PARSE",self.world.claim.scope,
            self.world.claim.project_id,self.world.claim.payload_refs,self.world.claim.trace_id,7,2)
        with self.assertRaises(OutputGenerationCompletionError):
            self.owner.complete(wrong,worker_ref="worker-1",publication=self.world.publication)
        self.assertEqual(self.world.calls,0)

    def test_publication_requires_all_four_passed_codes_and_matching_hash_proof(self):
        with self.assertRaises(OutputGenerationCompletionError):
            OutputArtifactPublication(
                uuid.uuid4(),self.world.execution_id,uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),
                bytes.fromhex("ab"*32),1,"image/png",
                (OutputValidationEvidence("FORMAT_CHECK","PASSED"),),
            )
        with self.assertRaises(OutputGenerationCompletionError):
            OutputArtifactPublication(
                uuid.uuid4(),self.world.execution_id,uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),
                bytes.fromhex("ab"*32),1,"image/png",
                tuple(OutputValidationEvidence(code,"PASSED",bytes.fromhex("cd"*32))
                      for code in ("FORMAT_CHECK","STRUCTURE_CHECK","HASH_CHECK","CONTENT_CHECK")),
            )


if __name__ == "__main__":
    unittest.main()
