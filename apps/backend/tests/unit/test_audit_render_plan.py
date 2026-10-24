import unittest
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.audit.application.render_plan import AuditRenderPlan,AuditExportWorkerRenderPlan
from plm_assistant.modules.audit.application.worker_capture import AuditExportCaptureCommand,AuditExportWorkerError
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
from plm_assistant.modules.audit.application.submit_export import AuditExportIntent,AcceptedAuditExport
from plm_assistant.modules.audit.application.capture_contract import CapturedAuditExport
from plm_assistant.modules.audit.application.current_export_authority import AuditExportCurrentAuthorityError
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.jobs.application.lease import ClaimedJob,JobLeaseError


class RenderPlanTests(unittest.TestCase):
    def setUp(self):
        self.value=AuditRenderPlan(uuid4(),uuid4(),uuid4(),1,1,"worker",uuid4(),0,"a"*64,"CAPTURE-MEMBERSHIP-V1",datetime.now(timezone.utc))

    def test_exact_types_and_closed_shape(self):
        for changes in (dict(file_id=uuid4().hex),dict(export_id=uuid4().__class__(int=0)),
                dict(fencing_token=True),dict(fencing_token=2**63),dict(attempt_no=True),
                dict(worker_ref="unsafe path"),dict(member_count=True),dict(member_count=100001),
                dict(membership_hash="A"*64),dict(membership_version="other"),
                dict(created_at=datetime.now())):
            with self.subTest(changes=changes),self.assertRaises(AuditExportWorkerError):replace(self.value,**changes)

    def test_invalid_command_never_enters_transaction(self):
        uow=Mock()
        service=AuditExportWorkerRenderPlan(plans=Mock(),unit_of_work=uow,repository=Mock(),
            authority=Mock(),queue=Mock(),leases=Mock(),captures=Mock())
        with self.assertRaises(AuditExportWorkerError):service.plan(True)
        command=AuditExportCaptureCommand(self.value.export_id,self.value.job_id,1,"worker")
        object.__setattr__(command,"fencing_token",True)
        with self.assertRaises(AuditExportWorkerError):service.plan(command)
        uow.assert_not_called()

    def test_required_plan_dependency(self):
        with self.assertRaises(ValueError):AuditExportWorkerRenderPlan(plans=None)

    def worker(self):
        now=self.value.created_at
        spec=AuditExportSpec('DEPLOYMENT',None,'SECURITY_REVIEW',now-timedelta(hours=1),now)
        intent=AuditExportIntent(self.value.export_id,uuid4(),uuid4(),now,spec,spec.fingerprint())
        accepted=AcceptedAuditExport(intent,self.value.job_id,uuid4(),uuid4(),now)
        capture=CapturedAuditExport(intent.export_id,intent.actor_id,'DEPLOYMENT',None,now,now,0,'a'*64,
            self.value.membership_version,intent.intent_hash,intent.policy_version,intent.projection_version,intent.format_version)
        tx=Mock();uow=Mock();uow.return_value.__enter__=Mock(return_value=tx);uow.return_value.__exit__=Mock(return_value=False)
        repo,authority,queue,leases,captures,plans=(Mock() for _ in range(6))
        authority=Mock(spec=['assert_current'])
        repo.peek_created.return_value=repo.get_created.return_value=intent
        repo.get_accepted.return_value=accepted;repo.is_retryable_deadlock.return_value=False
        authority.assert_current.return_value=None
        queue.find_export.return_value=AuditExportJobRef(accepted.job_id,accepted.event_id)
        claim=ClaimedJob(accepted.job_id,'AUDIT_EXPORT','DEPLOYMENT',None,dict(export_id=str(intent.export_id),policy_version=intent.policy_version),str(intent.trace_id),1,1)
        leases.check_current.return_value=claim;captures.read_capture.return_value=capture;plans.register.return_value=self.value
        service=AuditExportWorkerRenderPlan(plans=plans,unit_of_work=uow,repository=repo,authority=authority,queue=queue,leases=leases,captures=captures)
        command=AuditExportCaptureCommand(intent.export_id,accepted.job_id,1,'worker')
        return service,command,tx,authority,leases,captures,plans

    def test_only_read_capture_and_twice_current_checks(self):
        service,c,tx,auth,leases,captures,plans=self.worker()
        self.assertEqual(service.plan(c),self.value)
        captures.capture.assert_not_called();captures.read_capture.assert_called_once()
        self.assertEqual(auth.assert_current.call_count,2);self.assertEqual(leases.check_current.call_count,2)
        self.assertEqual(auth.assert_current.call_args.kwargs['request'].stage,'RENDER')
        tx.commit.assert_called_once()

    def test_missing_capture_never_registers_or_commits(self):
        service,c,tx,_,_,captures,plans=self.worker();captures.read_capture.return_value=None
        with self.assertRaises(AuditExportWorkerError):service.plan(c)
        plans.register.assert_not_called();tx.commit.assert_not_called()

    def test_wrong_plan_binding_rejected_even_if_port_returns_dto(self):
        for changes in (dict(export_id=uuid4()),dict(job_id=uuid4()),dict(fencing_token=2),
                dict(attempt_no=2),dict(worker_ref='other'),dict(member_count=1),
                dict(membership_hash='b'*64),dict(created_at=self.value.created_at-timedelta(seconds=1))):
            service,c,tx,_,_,_,plans=self.worker();plans.register.return_value=replace(self.value,**changes)
            with self.subTest(changes=changes),self.assertRaises(AuditExportWorkerError):service.plan(c)
            tx.commit.assert_not_called()

    def test_postcheck_revocation_and_stale_lease_no_commit(self):
        service,c,tx,auth,leases,_,_=self.worker()
        auth.assert_current.side_effect=[None,AuditExportCurrentAuthorityError('LICENSE_OPERATION_DENIED')]
        with self.assertRaises(AuditExportWorkerError) as caught:service.plan(c)
        self.assertEqual(caught.exception.code,'LICENSE_OPERATION_DENIED');tx.commit.assert_not_called()
        auth.assert_current.side_effect=None
        claim=leases.check_current.return_value
        leases.check_current.side_effect=[claim,JobLeaseError('STALE_LEASE')]
        with self.assertRaises(AuditExportWorkerError) as caught:service.plan(c)
        self.assertEqual(caught.exception.code,'STALE_LEASE');tx.commit.assert_not_called()

    def test_unknown_failure_not_blindly_retried_or_exposed(self):
        service,c,tx,_,_,_,plans=self.worker()
        plans.register.side_effect=RuntimeError('sensitive internal storage detail')
        with self.assertRaises(AuditExportWorkerError) as caught:service.plan(c)
        self.assertEqual(str(caught.exception),'AUDIT_UNAVAILABLE')
        self.assertEqual(plans.register.call_count,1);tx.commit.assert_not_called()
