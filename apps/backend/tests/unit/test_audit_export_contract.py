from dataclasses import replace,fields,FrozenInstanceError
from datetime import datetime,timezone,timedelta
import unittest
from uuid import uuid4,UUID
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec,AuditExportAuthorityRequest,EXPORT_PURPOSES


class AuditExportContractTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc)
        self.spec=AuditExportSpec("PROJECT",uuid4(),"PROJECT_GOVERNANCE",now-timedelta(days=1),now)

    def test_valid_project_and_deployment_purposes_and_fixed_batch(self):
        for purpose in EXPORT_PURPOSES:
            self.assertEqual(replace(self.spec,purpose=purpose).as_search().page_size,200)
            if purpose!="PROJECT_GOVERNANCE":self.assertEqual(replace(self.spec,scope="DEPLOYMENT",project_id=None,purpose=purpose).scope,"DEPLOYMENT")
        self.assertIsNone(self.spec.as_search().after)

    def test_scope_and_project_binding(self):
        for changes in (dict(scope="GLOBAL"),dict(scope="DEPLOYMENT"),dict(project_id=None),dict(project_id=UUID(int=0)),dict(project_id=True)):
            with self.assertRaises(ValueError):replace(self.spec,**changes)
        with self.assertRaises(ValueError):replace(self.spec,scope="DEPLOYMENT",project_id=None)

    def test_purpose_free_text_and_unsupported_rejected(self):
        for purpose in (None,True,"","security_review","please export private content","ANY"):
            with self.assertRaises(ValueError):replace(self.spec,purpose=purpose)

    def test_time_range_and_every_filter_revalidated(self):
        for changes in (dict(start_at=self.spec.end_at),dict(start_at=self.spec.end_at-timedelta(days=32)),dict(end_at=self.spec.end_at.replace(tzinfo=None)),
                        dict(action="free text"),dict(outcome="OTHER"),dict(actor_id=True),dict(target_object_type="anything"),dict(target_object_id=UUID(int=0)),dict(trace_id=True)):
            with self.assertRaises(ValueError):replace(self.spec,**changes)

    def test_equivalent_utc_has_same_fingerprint(self):
        offset=timezone(timedelta(hours=8))
        equivalent=replace(self.spec,start_at=self.spec.start_at.astimezone(offset),end_at=self.spec.end_at.astimezone(offset))
        self.assertEqual(equivalent.fingerprint(),self.spec.fingerprint())
        self.assertEqual(len(self.spec.fingerprint()),64)

    def test_fingerprint_binds_all_intent_fields(self):
        for changes in (dict(project_id=uuid4()),dict(purpose="COMPLIANCE_REVIEW"),dict(start_at=self.spec.start_at+timedelta(seconds=1)),
                        dict(end_at=self.spec.end_at+timedelta(seconds=1)),dict(action="OTHER"),dict(outcome="FAILED"),dict(actor_id=uuid4()),
                        dict(target_object_type="PRJ-01"),dict(target_object_id=uuid4()),dict(trace_id=uuid4())):
            self.assertNotEqual(replace(self.spec,**changes).fingerprint(),self.spec.fingerprint())
        corrupted=replace(self.spec);object.__setattr__(corrupted,"scope","GLOBAL")
        with self.assertRaises(ValueError):corrupted.fingerprint()

    def test_immutable_minimal_spec_has_no_tokens_or_arbitrary_fields(self):
        with self.assertRaises(FrozenInstanceError):self.spec.purpose="ANY"
        names={field.name for field in fields(self.spec)}
        self.assertFalse(names&{"session_token","csrf_token","path","fields","cursor","endpoint","purpose_note","payload"})

    def test_worker_coordinates_and_stage_are_not_permission_proof(self):
        request=AuditExportAuthorityRequest(uuid4(),uuid4(),"PROJECT",self.spec.project_id,"CAPTURE")
        for stage in ("CAPTURE","RENDER","PUBLISH"):self.assertEqual(replace(request,stage=stage).stage,stage)
        for changes in (dict(export_id=True),dict(actor_id=UUID(int=0)),dict(scope="GLOBAL"),dict(project_id=None),dict(stage="DOWNLOAD"),dict(stage=True)):
            with self.assertRaises(ValueError):replace(request,**changes)
        self.assertNotIn("authorized",{field.name for field in fields(request)})


if __name__=="__main__":unittest.main()
