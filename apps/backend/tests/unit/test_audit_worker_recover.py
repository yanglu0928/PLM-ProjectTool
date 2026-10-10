from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
from uuid import UUID,uuid4
from . import test_audit_worker_render as render_fixture
from plm_assistant.modules.audit.application.worker_recover import AuditExportWorkerRecover
from plm_assistant.modules.audit.application.worker_render import StagedAuditExport
from plm_assistant.modules.audit.application.worker_capture import AuditExportCaptureCommand,AuditExportWorkerError
from plm_assistant.modules.audit.infrastructure.render_plan_repository import SqlAlchemyAuditRenderPlans
from plm_assistant.modules.document.application.audit_export_metadata import AuditRegisteredFileRequest,AuditFileMetadataError
from plm_assistant.modules.document.infrastructure.audit_export_metadata import SqlAlchemyAuditExportFileMetadata
from plm_assistant.modules.jobs.application.audit_export_complete import AuditExportJobCompletion
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest,AuditExportJobRef
from plm_assistant.modules.jobs.application.lease import ClaimedJob


class WorkerRecoverTests(TestCase):
    def setUp(self):
        source=render_fixture.WorkerRenderTests();source.setUp()
        self.staged=StagedAuditExport(source.context,source.rendered,source.content)
        plan=source.context.plan
        self.command=AuditExportCaptureCommand(plan.export_id,plan.job_id,plan.fencing_token,plan.worker_ref)
        self.storage=Mock();self.identity=Mock(spec=['assert_current']);self.identity.assert_current.return_value=uuid4()
        self.worker=AuditExportWorkerRecover(files=Mock(),results=Mock(),completion=Mock(),audit=Mock(),system_actor=self.identity,
            source=Mock(),storage=self.storage,plans=Mock(),unit_of_work=Mock(),repository=Mock(),authority=Mock(),queue=Mock(),leases=Mock(),captures=Mock())

    def test_invalid_command_no_file_access(self):
        with self.assertRaises(AuditExportWorkerError):self.worker.recover(True)
        self.storage.inspect.assert_not_called();self.storage.promote.assert_not_called()

    def test_exact_registered_source_bounds_and_inactive_transaction(self):
        request=AuditRegisteredFileRequest(uuid4(),uuid4(),uuid4(),self.staged.content.coordinate)
        for changes in (dict(export_id=UUID(int=0)),dict(actor_id=True),dict(trace_id=None),dict(coordinate=None)):
            with self.assertRaises(AuditFileMetadataError):replace(request,**changes)
        with self.assertRaises(AuditFileMetadataError):SqlAlchemyAuditExportFileMetadata().read_registered(None,request=request)

    def test_plan_find_validation_before_database(self):
        for token in (None,True,0,-1,2**63):
            with self.assertRaises(AuditExportWorkerError):SqlAlchemyAuditRenderPlans().find(None,export_id=uuid4(),job_id=uuid4(),fencing_token=token)

    def test_recovery_physical_modes_and_no_rerender(self):
        self.worker._read=Mock(return_value=(self.staged,None));self.worker._preflight=Mock()
        self.worker._publish=Mock(return_value='published')
        self.storage.promote.return_value=self.staged.content
        for shape,mode in (('STAGE_ONLY','new'),('FINAL_VERIFIED','final_only'),('LINKED_PAIR','linked_pair')):
            self.storage.inspect.return_value=shape
            self.assertEqual(self.worker.recover(self.command),'published')
            self.storage.promote.assert_called_with(self.staged.content,mode=mode)
        self.storage.staging_sink.assert_not_called()
        for shape in ('NONE','FINAL_INVALID','BOTH_UNRELATED','UNSAFE'):
            self.storage.inspect.return_value=shape
            with self.assertRaises(AuditExportWorkerError) as caught:self.worker.recover(self.command)
            self.assertEqual(caught.exception.code,'AUDIT_EXPORT_CONTENT_UNAVAILABLE')

    def test_replay_reauthorizes_after_hash_without_physical_or_job_write(self):
        result=object();self.worker._read=Mock(return_value=(self.staged,result))
        self.worker._publish=Mock();self.storage.inspect.return_value='FINAL_VERIFIED'
        self.assertIs(self.worker.recover(self.command),result)
        self.assertEqual(self.worker._read.call_count,2)
        self.worker._publish.assert_not_called();self.storage.promote.assert_not_called()
        self.worker._read.side_effect=[(self.staged,result),(self.staged,object())]
        with self.assertRaises(AuditExportWorkerError):self.worker.recover(self.command)

    def test_terminal_job_port_reads_original_pair_never_finishes(self):
        intent=self.staged.context.intent;plan=self.staged.context.plan
        request=AuditExportJobRequest(intent.export_id,intent.actor_id,'DEPLOYMENT',None,intent.trace_id,intent.policy_version)
        refs=AuditExportJobRef(plan.job_id,uuid4());queue,leases=Mock(),Mock()
        queue.find_export.return_value=refs
        claim=ClaimedJob(plan.job_id,'AUDIT_EXPORT','DEPLOYMENT',None,dict(export_id=str(intent.export_id),policy_version=intent.policy_version),str(intent.trace_id),1,1)
        leases.check_succeeded.return_value=claim
        service=AuditExportJobCompletion(queue=queue,leases=leases)
        self.assertEqual(service.assert_succeeded(None,request=request,refs=refs,fencing_token=1,worker_ref='worker'),claim)
        leases.finish.assert_not_called();leases.check_current.assert_not_called()
