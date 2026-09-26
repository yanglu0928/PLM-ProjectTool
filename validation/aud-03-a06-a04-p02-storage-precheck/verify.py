"""Read-only owner/storage compatibility probes; no file or database mutation."""
import uuid
import unittest

from plm_assistant.modules.document.application.publish_file import (
    FilePublishError, FilePublishService, PublishFile,
)
from plm_assistant.modules.document.infrastructure.local_storage import (
    LocalFileStorage, LocalStorageError,
)
from plm_assistant.modules.document.infrastructure.orm import FileObjectRow


class StorageCompatibility(unittest.TestCase):
    def test_existing_scopes_remain_supported(self):
        for scope, project in (("GLOBAL", None), ("PROJECT", uuid.uuid4())):
            file_id = uuid.uuid4()
            staging, final = LocalFileStorage.locators(
                scope=scope, project_id=project, file_object_id=file_id,
            )
            self.assertEqual(staging, "temp/" + final)
            FilePublishService._validate(PublishFile(
                file_id, scope, project, uuid.uuid4(), uuid.uuid4(), 0, 1024,
            ))

    def test_deployment_storage_rejects(self):
        with self.assertRaises(LocalStorageError):
            LocalFileStorage.locators(
                scope="DEPLOYMENT", project_id=None, file_object_id=uuid.uuid4(),
            )

    def test_deployment_publish_rejects(self):
        with self.assertRaises(FilePublishError) as caught:
            FilePublishService._validate(PublishFile(
                uuid.uuid4(), "DEPLOYMENT", None, uuid.uuid4(), uuid.uuid4(), 0, 1024,
            ))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_metadata_scope_constraint_matches_boundary(self):
        constraints = {
            constraint.name: str(constraint.sqltext)
            for constraint in FileObjectRow.__table__.constraints
            if hasattr(constraint, "sqltext")
        }
        scope = constraints["ck_doc_file_objects__scope_project"]
        self.assertIn("'GLOBAL'", scope)
        self.assertIn("scope='PROJECT'", scope)
        # CR-AUD-002/0040 expands metadata only; ordinary publication stays closed.
        self.assertIn("DEPLOYMENT", scope)
        usage = constraints["ck_doc_file_objects__usage"]
        self.assertIn("usage_kind='DOCUMENT'", usage)
        self.assertIn("scope IN ('GLOBAL','PROJECT')", usage)


if __name__ == "__main__":
    unittest.main(verbosity=2)
