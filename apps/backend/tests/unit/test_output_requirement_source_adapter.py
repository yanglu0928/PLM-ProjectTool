from __future__ import annotations
import unittest, uuid
from plm_assistant.entrypoints.output_requirement_source_adapter import RequirementOutputSourceAdapter
from plm_assistant.modules.requirement.application.read_versions import RequirementOutputSourceProjection

class RequirementOutputSourceAdapterTests(unittest.TestCase):
    def test_maps_owner_authorized_fixed_version(self):
        project, version, actor = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        projection = RequirementOutputSourceProjection(version, project, "APPROVED", {"statement":"Synthetic"})
        class Reader:
            def read_output_source(self, transaction, **kwargs):
                self.kwargs=kwargs
                return projection
        reader=Reader()
        result=RequirementOutputSourceAdapter(reader).read_authorized_fixed_version(
            object(), actor_id=actor, project_id=project, source_version_ref=version)
        self.assertEqual(reader.kwargs, {"actor_id":actor,"project_id":project,"requirement_version_id":version})
        self.assertEqual(result.source_kind, "REQUIREMENT_VERSION")
        self.assertEqual(result.review_state, "APPROVED")
        self.assertTrue(result.authorized)
        self.assertEqual(result.fields["statement"], "Synthetic")

if __name__ == "__main__":
    unittest.main()
