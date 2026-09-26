from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.jobs.application.audit_export_claim import AuditExportClaims,AuditExportClaimCandidate
from plm_assistant.modules.jobs.application.lease import JobLeaseError


class ClaimReservationTests(TestCase):
    def setUp(self):
        self.repo=Mock(spec=['reserve_next','peek_next','claim_target'])
        self.owner=AuditExportClaims(repository=self.repo)
        self.tx=object()

    def test_explicit_reservation_not_unlocked_hint_or_mutation(self):
        candidate=AuditExportClaimCandidate(uuid4(),uuid4(),0)
        self.repo.reserve_next.return_value=candidate
        self.assertEqual(self.owner.reserve_next(self.tx),candidate)
        self.repo.reserve_next.assert_called_once_with(self.tx)
        self.repo.peek_next.assert_not_called();self.repo.claim_target.assert_not_called()
        self.repo.reserve_next.return_value=None
        self.assertIsNone(self.owner.reserve_next(self.tx))

    def test_bad_candidate_or_backend_exception_closed(self):
        self.repo.reserve_next.return_value=object()
        with self.assertRaises(JobLeaseError):self.owner.reserve_next(self.tx)
        self.repo.reserve_next.side_effect=RuntimeError('private connection data')
        with self.assertRaises(JobLeaseError) as cm:self.owner.reserve_next(self.tx)
        self.assertEqual(cm.exception.code,'JOB_STORE_UNAVAILABLE')
        self.assertNotIn('private',str(cm.exception))
        self.repo.claim_target.assert_not_called()
