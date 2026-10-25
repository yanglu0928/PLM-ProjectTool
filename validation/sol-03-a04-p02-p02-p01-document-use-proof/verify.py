"""Win11 disposable PG proof of opaque Document fixed-version use checks."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from plm_assistant.modules.document.application.prove_reference_use_document import (
    ReferenceUseDocumentError, ReferenceUseDocumentProofService,
)
from plm_assistant.modules.document.infrastructure.reference_use_source import (
    SqlAlchemyReferenceUseDocumentSource,
)


ROOT = Path(__file__).resolve().parents[2]


def module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


project_fixture = module(
    "project_reference_document_fixture",
    "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
global_fixture = module(
    "global_reference_document_fixture",
    "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")


def denied(action) -> None:
    try:
        action()
    except ReferenceUseDocumentError:
        pass
    else:
        raise AssertionError("unavailable fixed Document source was accepted")


def project_created(*, runtime, project, other_project, document_version,
                    scratch, locator, content, downloads, **_unused):
    service = ReferenceUseDocumentProofService(
        sources=SqlAlchemyReferenceUseDocumentSource(),
        storage=downloads._storage)  # test fixture's isolated storage only
    with runtime.unit_of_work() as tx:
        proof = service.prove(
            tx, scope="PROJECT", project_id=project,
            document_version_id=document_version)
        assert proof.document_version_id == document_version
        assert proof.scope == "PROJECT" and proof.project_id == project
        assert len(proof.content_sha256) == 32
        denied(lambda: service.prove(
            tx, scope="PROJECT", project_id=other_project,
            document_version_id=document_version))
        denied(lambda: service.prove(
            tx, scope="PROJECT", project_id=project,
            document_version_id=uuid.uuid4()))
    file = scratch / "private-documents" / locator
    original = file.read_bytes()
    try:
        file.write_bytes(b"X" * len(content))
        with runtime.unit_of_work() as tx:
            denied(lambda: service.prove(
                tx, scope="PROJECT", project_id=project,
                document_version_id=document_version))
    finally:
        file.write_bytes(original)
    with runtime.unit_of_work() as tx:
        assert service.prove(
            tx, scope="PROJECT", project_id=project,
            document_version_id=document_version).content_sha256 == proof.content_sha256
    return 0


def global_qualified(*, runtime, request, downloads, **_unused):
    service = ReferenceUseDocumentProofService(
        sources=SqlAlchemyReferenceUseDocumentSource(),
        storage=downloads._storage)  # no admin Session is passed
    with runtime.unit_of_work() as tx:
        for version_id in request.document_version_ids:
            proof = service.prove(
                tx, scope="GLOBAL", project_id=None,
                document_version_id=version_id)
            assert proof.scope == "GLOBAL" and proof.project_id is None
            assert len(proof.content_sha256) == 32
            denied(lambda: service.prove(
                tx, scope="PROJECT", project_id=uuid.uuid4(),
                document_version_id=version_id))


def main() -> None:
    project_fixture.main(on_created=project_created)
    global_fixture.main(on_qualified=global_qualified)
    print("SOL_03_A04_P02_P02_P01_DOCUMENT_USE_PROOF_PASS: PROJECT/GLOBAL "
          "fixed available version, physical bytes, isolation and tamper denial")


if __name__ == "__main__":
    main()
