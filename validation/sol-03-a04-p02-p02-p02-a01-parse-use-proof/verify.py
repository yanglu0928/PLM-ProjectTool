"""Win11 PG/real-file proof of internal fixed parser source verification."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from plm_assistant.modules.document.application.prove_reference_use_document import (
    ReferenceUseDocumentProofService,
)
from plm_assistant.modules.document.application.prove_reference_use_parse import (
    ReferenceUseParseError, ReferenceUseParseProofService,
)
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import (
    SqlAlchemyParseResultReadRepository,
)
from plm_assistant.modules.document.infrastructure.reference_use_source import (
    SqlAlchemyReferenceUseDocumentSource,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_parse_reference_fixture",
    ROOT / "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def check(*, runtime, request, downloads, parse_results, **_unused):
    documents = ReferenceUseDocumentProofService(
        sources=SqlAlchemyReferenceUseDocumentSource(),
        storage=downloads._storage)  # isolated fixture storage
    metadata = SqlAlchemyParseResultReadRepository()
    service = ReferenceUseParseProofService(
        documents=documents, metadata=metadata,
        storage=parse_results._storage)  # isolated fixture storage
    with runtime.unit_of_work() as tx:
        evidence = SqlAlchemyEvidenceFixedSourceRepository().get_for_trace(
            tx, scope="GLOBAL", project_id=None, evidence_id=request.evidence_ids[1])
        assert evidence is not None and evidence.source_parse_record_id is not None
        parsed = service.prove(
            tx, scope="GLOBAL", project_id=None,
            document_version_id=evidence.document_version_id,
            parse_record_id=evidence.source_parse_record_id)
        assert parsed.source_sha256 == documents.prove(
            tx, scope="GLOBAL", project_id=None,
            document_version_id=evidence.document_version_id).content_sha256
        assert parsed.result_sha256 and parsed.content
        row = metadata.get_for_trace(
            tx, scope="GLOBAL", project_id=None,
            document_version_id=evidence.document_version_id,
            parse_record_id=evidence.source_parse_record_id)
        assert row is not None
    path = parse_results._storage._root / row.storage_locator
    original = path.read_bytes()
    try:
        path.write_bytes(original[:-1] + b"!")
        with runtime.unit_of_work() as tx:
            try:
                service.prove(
                    tx, scope="GLOBAL", project_id=None,
                    document_version_id=evidence.document_version_id,
                    parse_record_id=evidence.source_parse_record_id)
            except ReferenceUseParseError:
                pass
            else:
                raise AssertionError("tampered parser result was accepted")
    finally:
        path.write_bytes(original)
    with runtime.unit_of_work() as tx:
        assert service.prove(
            tx, scope="GLOBAL", project_id=None,
            document_version_id=evidence.document_version_id,
            parse_record_id=evidence.source_parse_record_id).content == original


def main() -> None:
    fixture.main(on_qualified=check)
    print("SOL_03_A04_P02_P02_P02_A01_PARSE_USE_PROOF_PASS: current GLOBAL "
          "Document/ParseResult bytes, source binding and tamper rejection")


if __name__ == "__main__":
    main()
