from __future__ import annotations

import unittest
import uuid
from contextlib import contextmanager
from dataclasses import replace

from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.output.application.job_admission import (
    OutputExecutionAdmission,
    OutputJobAdmissionError,
    OutputJobAdmissionFacts,
    OutputJobExecutionAdmissionOwner,
)
from plm_assistant.modules.output.application.resolve_context import (
    PluginOperationCapability,
)
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)


class FakeRepository:
    def __init__(self, facts: OutputJobAdmissionFacts | None) -> None:
        self.facts = facts
        self.calls = 0
        self.transactions = []

    def load(self, transaction, **kwargs):
        self.calls += 1
        self.transactions.append(transaction)
        return self.facts


class FakeCapabilities:
    def __init__(self, value) -> None:
        self.value = value
        self.calls = 0
        self.transactions = []

    def get_operation(self, transaction, *, operation_id):
        self.calls += 1
        self.transactions.append(transaction)
        return self.value


@contextmanager
def unit_of_work():
    yield object()


def fixtures():
    job_id, project_id, request_id, snapshot_id = (uuid.uuid4() for _ in range(4))
    source_ref, template_ref = uuid.uuid4(), uuid.uuid4()
    payload = {"source": {"title": "synthetic"}}
    context_fingerprint = canonical_payload_fingerprint(payload)
    input_fingerprint = canonical_payload_fingerprint({
        "project_id": str(project_id), "output_type": "DOCX",
        "template_version_ref": str(template_ref),
        "source_version_refs": [str(source_ref)],
        "output_policy_ref": "POLICY-1", "plugin_operation": "doc.generate",
        "context_fingerprint": context_fingerprint.hex(),
    })
    facts = OutputJobAdmissionFacts(
        output_request_id=request_id, project_id=project_id, job_id=job_id,
        context_snapshot_id=snapshot_id, request_state="QUEUED", output_type="DOCX",
        template_version_ref=template_ref, source_version_refs=(source_ref,),
        output_policy_ref="POLICY-1", plugin_operation="doc.generate",
        input_fingerprint=input_fingerprint, context_payload=payload,
        context_fingerprint=context_fingerprint,
    )
    claim = ClaimedJob(
        job_id=job_id, job_type="OUTPUT_GENERATE", scope="PROJECT",
        project_id=project_id,
        payload_refs={"output_request_id": str(request_id),
                      "context_snapshot_id": str(snapshot_id)},
        trace_id=str(uuid.uuid4()), fencing_token=1, attempt_no=1,
    )
    capability = PluginOperationCapability(
        operation_id="doc.generate", output_types=("DOCX",),
        enabled=True, trusted=True,
    )
    return claim, facts, capability


class TestOutputJobAdmission(unittest.TestCase):
    def create_owner(self, facts, capability):
        repository = FakeRepository(facts)
        capabilities = FakeCapabilities(capability)
        owner = OutputJobExecutionAdmissionOwner(
            unit_of_work=unit_of_work, repository=repository,
            plugin_capabilities=capabilities,
        )
        return owner, repository, capabilities

    def test_valid_admission_returns_only_minimal_request_facts(self) -> None:
        claim, facts, capability = fixtures()
        owner, repository, capabilities = self.create_owner(facts, capability)

        result = owner.admit(claim)

        self.assertIs(type(result), OutputExecutionAdmission)
        self.assertEqual(result.output_request_id, facts.output_request_id)
        self.assertEqual(result.context_snapshot_id, facts.context_snapshot_id)
        self.assertEqual(result.input_fingerprint, facts.input_fingerprint)
        self.assertFalse(hasattr(result, "context_payload"))
        self.assertEqual(repository.calls, 1)
        self.assertEqual(capabilities.calls, 1)

    def test_in_transaction_uses_caller_transaction_without_opening_uow(self) -> None:
        claim, facts, capability = fixtures()
        repository = FakeRepository(facts)
        capabilities = FakeCapabilities(capability)
        owner = OutputJobExecutionAdmissionOwner(
            unit_of_work=lambda: (_ for _ in ()).throw(
                AssertionError("nested UnitOfWork must not be opened")
            ),
            repository=repository, plugin_capabilities=capabilities,
        )
        transaction = object()

        result = owner.admit_in_transaction(transaction, claim)

        self.assertIs(type(result), OutputExecutionAdmission)
        self.assertEqual(repository.calls, 1)
        self.assertEqual(capabilities.calls, 1)
        self.assertIs(repository.transactions[0], transaction)
        self.assertIs(capabilities.transactions[0], transaction)

    def test_missing_transaction_fails_before_repository_read(self) -> None:
        claim, facts, capability = fixtures()
        owner, repository, capabilities = self.create_owner(facts, capability)
        with self.assertRaises(OutputJobAdmissionError):
            owner.admit_in_transaction(None, claim)
        self.assertEqual(repository.calls, 0)
        self.assertEqual(capabilities.calls, 0)

    def test_invalid_claims_are_rejected_before_repository_read(self) -> None:
        claim, facts, capability = fixtures()
        mutations = (
            replace(claim, job_type="AUDIT_EXPORT"),
            replace(claim, scope="GLOBAL"),
            replace(claim, payload_refs={**claim.payload_refs, "extra": "bad"}),
            replace(claim, fencing_token=0),
        )
        for invalid_claim in mutations:
            with self.subTest(claim=invalid_claim):
                owner, repository, capabilities = self.create_owner(facts, capability)
                with self.assertRaises(OutputJobAdmissionError):
                    owner.admit(invalid_claim)
                self.assertEqual(repository.calls, 0)
                self.assertEqual(capabilities.calls, 0)

    def test_binding_state_and_both_fingerprints_are_checked(self) -> None:
        claim, facts, capability = fixtures()
        mutations = (
            {"output_request_id": uuid.uuid4()},
            {"project_id": uuid.uuid4()},
            {"job_id": uuid.uuid4()},
            {"context_snapshot_id": uuid.uuid4()},
            {"request_state": "CANCELLED"},
            {"input_fingerprint": b"x" * 32},
            {"context_fingerprint": b"x" * 32},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                owner, _, _ = self.create_owner(replace(facts, **mutation), capability)
                with self.assertRaises(OutputJobAdmissionError):
                    owner.admit(claim)

    def test_missing_disabled_untrusted_or_incompatible_plugin_fails_closed(self) -> None:
        claim, facts, _ = fixtures()
        invalid_capabilities = (
            None,
            PluginOperationCapability(
                operation_id="doc.generate", output_types=("DOCX",),
                enabled=False, trusted=True,
            ),
            PluginOperationCapability(
                operation_id="doc.generate", output_types=("DOCX",),
                enabled=True, trusted=False,
            ),
            PluginOperationCapability(
                operation_id="doc.generate", output_types=("PPTX",),
                enabled=True, trusted=True,
            ),
        )
        for capability in invalid_capabilities:
            with self.subTest(capability=capability):
                owner, _, _ = self.create_owner(facts, capability)
                with self.assertRaises(OutputJobAdmissionError):
                    owner.admit(claim)


if __name__ == "__main__":
    unittest.main()
