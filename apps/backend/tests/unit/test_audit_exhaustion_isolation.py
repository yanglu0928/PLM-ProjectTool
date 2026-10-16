from datetime import datetime,timezone
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from . import test_audit_exhaustion_sweep as fixture
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_export_exhaustion_scan import AuditExportExhaustionCursor,AuditExportExhaustionScan,AuditExportExhaustionCandidates
from plm_assistant.modules.jobs.application.lease import JobLeaseError


class ExhaustionIsolationTests(TestCase):
    def setUp(self):
        self.f=fixture.SweepTests();self.f.setUp()
        self.cursor=AuditExportExhaustionCursor(datetime.now(timezone.utc),self.f.candidate.job_id)
        self.f.candidates.scan_next.return_value=AuditExportExhaustionScan(self.cursor,self.f.candidate)
        self.f.owner.inspect_source.return_value=None

    def test_bad_ref_advance_no_owner_and_end_reset(self):
        self.f.candidates.scan_next.return_value=AuditExportExhaustionScan(self.cursor,None,'INVALID_EXPORT_REF')
        self.assertEqual(self.f.sweep.run_next(isolate_sources=True).reason_code,'INVALID_EXPORT_REF')
        self.f.owner.inspect_source.assert_not_called();self.f.owner.expire.assert_not_called()
        self.f.candidates.scan_next.return_value=None
        self.assertIsNone(self.f.sweep.run_next(isolate_sources=True))
        self.assertIs(self.f.candidates.scan_next.call_args.kwargs['after'],self.cursor)
        self.assertIsNone(self.f.sweep._cursor)

    def test_source_problem_no_expire_unknown_problem_not_swallowed(self):
        self.f.owner.inspect_source.return_value='ROOT_MISSING'
        self.assertEqual(self.f.sweep.run_next(isolate_sources=True).reason_code,'ROOT_MISSING')
        self.f.owner.expire.assert_not_called()
        self.f.owner.inspect_source.side_effect=RuntimeError('private database')
        with self.assertRaises(AuditExportWorkerError):self.f.sweep.run_next(isolate_sources=True)
        self.f.owner.expire.assert_not_called()

    def test_original_owner_confirmation_still_required(self):
        self.f.owner.expire.side_effect=AuditExportWorkerError()
        self.assertEqual(self.f.sweep.run_next(isolate_sources=True),self.f.proof)
        self.f.owner.verify.assert_called_once()
        self.f.t.f.tx.commit.assert_not_called()

    def test_source_cursor_survives_success_and_window_refreshes(self):
        good=self.f.candidates.scan_next.return_value
        self.f.candidates.scan_next.side_effect=[AuditExportExhaustionScan(self.cursor,None,'INVALID_EXPORT_REF')]+[good]*32
        for _ in range(33):self.f.sweep.run_next(isolate_sources=True)
        calls=self.f.candidates.scan_next.call_args_list
        self.assertTrue(all(c.kwargs['after'] is self.cursor for c in calls[1:32]))
        self.assertIsNone(calls[32].kwargs['after'])

    def test_identity_after_scan_and_strict_port(self):
        self.f.t.t.actor.assert_current.side_effect=[uuid4(),uuid4()]
        with self.assertRaises(AuditExportWorkerError):self.f.sweep.run_next(isolate_sources=True)
        self.f.owner.inspect_source.assert_not_called()
        repo=Mock();port=AuditExportExhaustionCandidates(repository=repo)
        with self.assertRaises(JobLeaseError):port.scan_next(object(),after=object())
        repo.scan_next.assert_not_called()
        repo.scan_next.return_value=object()
        with self.assertRaises(JobLeaseError):port.scan_next(object())

    def test_real_owner_inspection_readonly_and_error_boundary(self):
        owner=self.f.t.owner
        self.assertIsNone(owner.inspect_source(self.f.t.f.cmd))
        self.f.t.t.failure.exhaustion.assert_not_called();self.f.t.f.tx.commit.assert_not_called()
        self.f.t.f.repo.get_created.return_value=None
        self.assertEqual(owner.inspect_source(self.f.t.f.cmd),'ROOT_MISSING')
        self.f.t.f.repo.get_created.side_effect=RuntimeError('private SQL')
        with self.assertRaises(AuditExportWorkerError) as cm:owner.inspect_source(self.f.t.f.cmd)
        self.assertNotIn('private',str(cm.exception))
