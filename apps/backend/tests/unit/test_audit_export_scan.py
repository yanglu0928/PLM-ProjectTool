from datetime import datetime,timezone
from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.jobs.application.audit_export_scan import AuditExportScanCursor,AuditExportScanReservation
from plm_assistant.modules.jobs.application.audit_export_claim import AuditExportClaims,AuditExportClaimCandidate
from plm_assistant.modules.jobs.application.lease import JobLeaseError


class ExportScanTests(TestCase):
    def setUp(self):
        self.cursor=AuditExportScanCursor(0,datetime.now(timezone.utc),uuid4())
        self.repo=Mock(spec=['scan_next']);self.owner=AuditExportClaims(repository=self.repo)

    def test_cursor_and_envelope_strict(self):
        for changes in ({'priority':True},{'priority':2**31},{'available_at':datetime.now()},{'job_id':uuid4().hex}):
            with self.assertRaises(JobLeaseError):replace(self.cursor,**changes)
        candidate=AuditExportClaimCandidate(self.cursor.job_id,uuid4(),0)
        AuditExportScanReservation(self.cursor,candidate)
        AuditExportScanReservation(self.cursor,None,'INVALID_EXPORT_REF')
        for c,reason in ((None,None),(candidate,'INVALID_EXPORT_REF'),(replace(candidate,job_id=uuid4()),None)):
            with self.assertRaises(JobLeaseError):AuditExportScanReservation(self.cursor,c,reason)

    def test_port_validates_and_passes_exact_cursor(self):
        value=AuditExportScanReservation(self.cursor,None,'INVALID_EXPORT_REF');self.repo.scan_next.return_value=value
        self.assertEqual(self.owner.scan_next(object(),after=self.cursor),value)
        self.assertIs(self.repo.scan_next.call_args.kwargs['after'],self.cursor)
        self.repo.scan_next.reset_mock()
        with self.assertRaises(JobLeaseError):self.owner.scan_next(object(),after=object())
        self.repo.scan_next.assert_not_called()

    def test_backend_failure_not_classified_as_bad_source(self):
        self.repo.scan_next.side_effect=RuntimeError('private database secret')
        with self.assertRaises(JobLeaseError) as cm:self.owner.scan_next(object())
        self.assertEqual(cm.exception.code,'JOB_STORE_UNAVAILABLE')
        self.repo.scan_next.side_effect=None;self.repo.scan_next.return_value=object()
        with self.assertRaises(JobLeaseError):self.owner.scan_next(object())
