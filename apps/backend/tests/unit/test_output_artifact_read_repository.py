from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from plm_assistant.modules.output.infrastructure.read_artifact_repository import (
    SqlAlchemyOutputArtifactReadRepository,
)


class Result:
    def __init__(self, row):
        self.row = row
    def one_or_none(self):
        return self.row


class StubSession(Session):
    def __init__(self, row):
        self.row, self.statement = row, None
    def in_transaction(self):
        return True
    def execute(self, statement):
        self.statement = statement
        return Result(self.row)


class OutputArtifactReadRepositoryTests(unittest.TestCase):
    def test_query_binds_exact_project_request_and_only_available_verified_chain(self):
        project, request = uuid.uuid4(), uuid.uuid4()
        ids = [uuid.uuid4() for _ in range(5)]
        row = SimpleNamespace(
            output_artifact_id=ids[0], output_request_id=request,
            project_id=project, document_id=ids[1], document_version_id=ids[2],
            artifact_kind="DOCX",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            artifact_sha256=bytes.fromhex("a7" * 32), size_bytes=44,
        )
        session = StubSession(row)
        result = SqlAlchemyOutputArtifactReadRepository().get_available(
            SimpleNamespace(session=session), project_id=project,
            output_request_id=request,
        )
        compiled = session.statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        self.assertIn("out_output_requests.request_state =", sql)
        self.assertIn("out_artifacts.artifact_state =", sql)
        self.assertIn("doc_document_versions.availability_state =", sql)
        self.assertIn("doc_file_objects.file_state =", sql)
        self.assertIn("doc_documents.document_category =", sql)
        self.assertEqual(set(compiled.params.values()), {project, request, "SUCCEEDED",
            "AVAILABLE", "PROJECT", "GENERATED_ARTIFACT", "ACTIVE",
            "PERSISTENT", "DOCUMENT"})

    def test_missing_available_chain_returns_none(self):
        session = StubSession(None)
        result = SqlAlchemyOutputArtifactReadRepository().get_available(
            SimpleNamespace(session=session), project_id=uuid.uuid4(),
            output_request_id=uuid.uuid4(),
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
