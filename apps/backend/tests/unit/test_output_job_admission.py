from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import replace

import pytest

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

    def load(self, transaction, **kwargs):
        self.calls += 1
        return self.facts


class FakeCapabilities:
    def __init__(self, value) -> None:
        self.value = value
        self.calls = 0

    def get_operation(self, transaction, *, operation_id):
        self.calls += 1
        return self.value


@contextmanager
def unit_of_work():
    yield object()


def fixtures():
    job_id, project_id, request_id, snapshot_id = (uuid.uuid4() for _ in range(4))
    source_ref, template_ref = uuid.uuid4(), uuid.uuid4()
    payload = {"source": {"title": "synthetic"}}
    input_fingerprint = canonical_payload_fingerprint({
        "project_id": str(project_id), "output_type": "DOCX",
        "template_version_ref": str(template_ref),
        "source_version_refs": [str(source_ref)],
        "output_policy_ref": "POLICY-1", "plugin_operation": "doc.generate",
        "context_fingerprint": canonical_payload_fingerprint(payload).hex(),
    })
    facts = OutputJobAdmissionFacts(
        output_request_id=request_id, project_id=project_id, job_id=job_id,
        context_snapshot_id=snapshot_id, request_state="QUEUED", output_type="DOCX",
        template_version_ref=template_ref, source_version_refs=(source_ref,),
        output_policy_ref="POLICY-1", plugin_operation="doc.generate",
        input_fingerprint=input_fingerprint, context_payload=payload,
        context_fingerprint=canonical_payload_fingerprint(payload),
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


def test_output_job_admission_returns_only_minimal_request_facts() -> None:
    claim, facts, capability = fixtures()
    repository, capabilities = FakeRepository(facts), FakeCapabilities(capability)
    owner = OutputJobExecutionAdmissionOwner(
        unit_of_work=unit_of_work, repository=repository,
        plugin_capabilities=capabilities,
    )

    result = owner.admit(claim)

    assert type(result) is OutputExecutionAdmission
    assert result.output_request_id == facts.output_request_id
    assert result.context_snapshot_id == facts.context_snapshot_id
    assert result.input_fingerprint == facts.input_fingerprint
    assert not hasattr(result, "context_payload")
    assert repository.calls == capabilities.calls == 1


@pytest.mark.parametrize("mutation", [
    lambda claim: replace(claim, job_type="AUDIT_EXPORT"),
    lambda claim: replace(claim, scope="GLOBAL"),
    lambda claim: replace(claim, payload_refs={**claim.payload_refs, "extra": "bad"}),
    lambda claim: replace(claim, fencing_token=0),
])
def test_output_job_admission_rejects_invalid_claim_before_read(mutation) -> None:
    claim, facts, capability = fixtures()
    repository, capabilities = FakeRepository(facts), FakeCapabilities(capability)
    owner = OutputJobExecutionAdmissionOwner(
        unit_of_work=unit_of_work, repository=repository,
        plugin_capabilities=capabilities,
    )

    with pytest.raises(OutputJobAdmissionError):
        owner.admit(mutation(claim))

    assert repository.calls == capabilities.calls == 0


@pytest.mark.parametrize("field,value", [
    ("output_request_id", uuid.uuid4()),
    ("project_id", uuid.uuid4()),
    ("job_id", uuid.uuid4()),
    ("context_snapshot_id", uuid.uuid4()),
    ("request_state", "CANCELLED"),
    ("input_fingerprint", b"x" * 32),
    ("context_fingerprint", b"x" * 32),
])
def test_output_job_admission_fails_closed_on_binding_or_snapshot_mismatch(field, value) -> None:
    claim, facts, capability = fixtures()
    repository = FakeRepository(replace(facts, **{field: value}))
    owner = OutputJobExecutionAdmissionOwner(
        unit_of_work=unit_of_work, repository=repository,
        plugin_capabilities=FakeCapabilities(capability),
    )

    with pytest.raises(OutputJobAdmissionError):
        owner.admit(claim)


@pytest.mark.parametrize("capability", [
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
])
def test_output_job_admission_fails_closed_when_current_plugin_capability_is_unavailable(capability) -> None:
    claim, facts, _ = fixtures()
    owner = OutputJobExecutionAdmissionOwner(
        unit_of_work=unit_of_work, repository=FakeRepository(facts),
        plugin_capabilities=FakeCapabilities(capability),
    )

    with pytest.raises(OutputJobAdmissionError):
        owner.admit(claim)
