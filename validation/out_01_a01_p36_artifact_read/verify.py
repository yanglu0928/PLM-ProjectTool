from __future__ import annotations

import uuid
from types import SimpleNamespace

from sqlalchemy.orm import Session

from plm_assistant.modules.output.infrastructure.read_artifact_repository import (
    SqlAlchemyOutputArtifactReadRepository,
)


def verify_available_artifact_reference(
    engine, *, project_id: uuid.UUID, output_request_id: uuid.UUID,
    output_artifact_id: uuid.UUID, document_id: uuid.UUID,
    document_version_id: uuid.UUID, content_sha256: bytes, size_bytes: int,
) -> dict[str, str]:
    """Exercise the production read repository against P33 committed PG18 facts."""
    repository = SqlAlchemyOutputArtifactReadRepository()
    with Session(engine, expire_on_commit=False) as session:
        with session.begin():
            reference = repository.get_available(
                SimpleNamespace(session=session), project_id=project_id,
                output_request_id=output_request_id,
            )
            if (reference is None
                    or reference.output_artifact_id != output_artifact_id
                    or reference.output_request_id != output_request_id
                    or reference.project_id != project_id
                    or reference.document_id != document_id
                    or reference.document_version_id != document_version_id
                    or reference.content_sha256 != content_sha256.hex()
                    or reference.size_bytes != size_bytes
                    or reference.artifact_kind != "DOCX"):
                raise AssertionError("P36 repository did not return the exact AVAILABLE binding")
            if repository.get_available(
                    SimpleNamespace(session=session), project_id=uuid.uuid4(),
                    output_request_id=output_request_id) is not None:
                raise AssertionError("P36 repository disclosed artifact across Project")
            if repository.get_available(
                    SimpleNamespace(session=session), project_id=project_id,
                    output_request_id=uuid.uuid4()) is not None:
                raise AssertionError("P36 repository disclosed artifact across request")
    return {
        "status": "PASS_SCOPE_LIMITED",
        "available_binding": "PASS",
        "cross_project_hidden": "PASS",
        "unknown_request_hidden": "PASS",
    }
