"""Disposable Win11 PG/real-file proof of internal Evidence reference use."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from plm_assistant.modules.document.application.prove_reference_use_document import (
    ReferenceUseDocumentProofService,
)
from plm_assistant.modules.document.application.prove_reference_use_parse import (
    ReferenceUseParseProofService,
)
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import (
    SqlAlchemyParseResultReadRepository,
)
from plm_assistant.modules.document.infrastructure.reference_use_source import (
    SqlAlchemyReferenceUseDocumentSource,
)
from plm_assistant.modules.evidence.application.prove_reference_use_evidence import (
    ReferenceUseEvidenceError, ReferenceUseEvidenceProofService,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


project_fixture = module(
    "project_evidence_use_fixture",
    "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
global_fixture = module(
    "global_evidence_use_fixture",
    "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")


def service(downloads, parse_results):
    documents = ReferenceUseDocumentProofService(
        sources=SqlAlchemyReferenceUseDocumentSource(),
        storage=downloads._storage)  # isolated fixture storage
    parses = ReferenceUseParseProofService(
        documents=documents, metadata=SqlAlchemyParseResultReadRepository(),
        storage=parse_results._storage)  # isolated fixture storage
    return ReferenceUseEvidenceProofService(
        evidence=SqlAlchemyEvidenceFixedSourceRepository(),
        documents=documents, parses=parses)


def denied(action) -> None:
    try:
        action()
    except ReferenceUseEvidenceError:
        pass
    else:
        raise AssertionError("unavailable Evidence reference use accepted")


def project_created(*, runtime, evidence, project, other_project, downloads,
                    parse_results, scratch, locator, content, **_unused):
    proof = service(downloads, parse_results)
    with runtime.unit_of_work() as tx:
        result = proof.prove(
            tx, scope="PROJECT", project_id=project, evidence_id=evidence)
        assert result.evidence_id == evidence and len(result.content_fingerprint) == 32
        denied(lambda: proof.prove(
            tx, scope="PROJECT", project_id=other_project, evidence_id=evidence))
    file = scratch / "private-documents" / locator
    original = file.read_bytes()
    try:
        file.write_bytes(b"X" * len(content))
        with runtime.unit_of_work() as tx:
            denied(lambda: proof.prove(
                tx, scope="PROJECT", project_id=project, evidence_id=evidence))
    finally:
        file.write_bytes(original)
    return 0


def global_qualified(*, runtime, request, downloads, parse_results, **_unused):
    proof = service(downloads, parse_results)
    with runtime.unit_of_work() as tx:
        results = tuple(proof.prove(
            tx, scope="GLOBAL", project_id=None, evidence_id=evidence_id)
            for evidence_id in request.evidence_ids)
        assert len(results) == 2
        assert results[0].content_fingerprint != results[1].content_fingerprint
        denied(lambda: proof.prove(
            tx, scope="PROJECT", project_id=uuid.uuid4(),
            evidence_id=request.evidence_ids[1]))
        source = SqlAlchemyEvidenceFixedSourceRepository().get_for_trace(
            tx, scope="GLOBAL", project_id=None,
            evidence_id=request.evidence_ids[1])
        assert source is not None and source.source_parse_record_id is not None
        metadata = SqlAlchemyParseResultReadRepository().get_for_trace(
            tx, scope="GLOBAL", project_id=None,
            document_version_id=source.document_version_id,
            parse_record_id=source.source_parse_record_id)
        assert metadata is not None
    file = parse_results._storage._root / metadata.storage_locator
    original = file.read_bytes()
    try:
        file.write_bytes(original[:-1] + b"!")
        with runtime.unit_of_work() as tx:
            denied(lambda: proof.prove(
                tx, scope="GLOBAL", project_id=None,
                evidence_id=request.evidence_ids[1]))
    finally:
        file.write_bytes(original)
    with runtime.unit_of_work() as tx:
        assert proof.prove(
            tx, scope="GLOBAL", project_id=None,
            evidence_id=request.evidence_ids[1]).content_fingerprint == results[1].content_fingerprint


def main() -> None:
    project_fixture.main(on_created=project_created)
    global_fixture.main(on_qualified=global_qualified)
    print("SOL_03_A04_P02_P02_P02_A02_EVIDENCE_USE_PROOF_PASS: PROJECT/GLOBAL "
          "DOCUMENT and parsed-node locator fingerprints, isolation and tamper denial")


if __name__ == "__main__":
    main()
