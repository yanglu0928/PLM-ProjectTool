from dataclasses import replace
from datetime import datetime,timezone,timedelta
from unittest.mock import Mock
from uuid import uuid4
import unittest
from plm_assistant.modules.audit.application.authorized_read import (
    AuthorizedAuditReadService,AuthorizedAuditReadError,AuditListQuery,AuditGetQuery,_BoundAccess,
)
from plm_assistant.modules.audit.application.queries.audit_query import AuditSearch,AuditEventView,AuditPage,AuditPosition
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction


class AuditAuthorizedReadTests(unittest.TestCase):
    def setUp(self):
        self.now,self.actor,self.project=datetime.now(timezone.utc),uuid4(),uuid4()
        self.tx=Mock();self.tx.__enter__=Mock(return_value=self.tx);self.tx.__exit__=Mock(return_value=False)
        self.access,self.admin,self.projects,self.guard,self.repo=Mock(),Mock(),Mock(),Mock(),Mock()
        self.access.authenticated_user.return_value=self.actor
        self.admin.authorized_admin.return_value=self.actor
        self.projects.require_in_transaction.side_effect=lambda tx,**k:AuthorizedProjectAction(self.actor,self.project,k["operation"],"PROJECT_MANAGER")
        self.search=AuditSearch(self.now-timedelta(days=1),self.now+timedelta(days=1),page_size=2)
        self.q=AuditListQuery(b"s"*32,self.project,uuid4(),self.search)
        self.view=AuditEventView(uuid4(),self.now,uuid4(),"PROJECT",self.project,"USER",self.actor,None,
            "REVIEW_DECISION_RECORDED","SUCCESS","review","RVW-02",uuid4(),None,None,"IN_REVIEW","APPROVED")
        self.repo.list_events.return_value=AuditPage((self.view,),None,False)
        self.repo.get_event.return_value=self.view
        self.service=AuthorizedAuditReadService(unit_of_work=lambda:self.tx,project_access=self.access,deployment_access=self.admin,
            projects=self.projects,license_guard=self.guard,repository=self.repo,clock=lambda:self.now)

    def test_project_list_get_current_proof_same_tx_no_commit(self):
        page=self.service.list(self.q)
        self.assertEqual(page.items,(self.view,))
        detail=self.service.get(AuditGetQuery(self.q.session_token,self.project,self.q.trace_id,self.view.audit_event_id))
        self.assertEqual(detail,self.view)
        self.assertEqual(self.projects.require_in_transaction.call_args.kwargs["operation"],"AUDIT_PROJECT_GET")
        self.assertIs(self.repo.get_event.call_args.args[0],self.tx)
        self.tx.commit.assert_not_called()
        self.admin.authorized_admin.assert_not_called()
        context=self.service.list_with_actor(self.q)
        self.assertEqual(context.actor_id,self.actor)
        self.assertEqual(context.project_id,self.project)
        self.assertEqual(context.page.items,(self.view,))

    def test_deployment_explicit_scope_no_project_fallback(self):
        self.repo.list_events.return_value=AuditPage((replace(self.view,event_scope="DEPLOYMENT",target_project_id=None),),None,False)
        self.assertEqual(self.service.list(replace(self.q,project_id=None)).items[0].event_scope,"DEPLOYMENT")
        self.access.authenticated_user.assert_not_called()
        self.projects.require_in_transaction.assert_not_called()
        self.admin.authorized_admin.return_value=None
        with self.assertRaisesRegex(AuthorizedAuditReadError,"AUTH_ACCESS_DENIED"):self.service.list(replace(self.q,project_id=None))

    def test_current_role_or_revoked_session_denies_before_query(self):
        self.access.authenticated_user.return_value=None
        with self.assertRaisesRegex(AuthorizedAuditReadError,"AUTH_ACCESS_DENIED"):self.service.list(self.q)
        self.access.authenticated_user.return_value=self.actor
        self.projects.require_in_transaction.side_effect=lambda tx,**k:AuthorizedProjectAction(self.actor,self.project,k["operation"],"CUSTOMER_MANAGER")
        with self.assertRaisesRegex(AuthorizedAuditReadError,"RESOURCE_NOT_FOUND"):self.service.list(self.q)
        self.repo.list_events.assert_not_called()

    def test_scope_detail_identifier_and_unsafe_summary_rejected(self):
        for bad in (replace(self.view,target_project_id=uuid4()),replace(self.view,reason_code="private free text"),
                    replace(self.view,audit_event_id=uuid4())):
            self.repo.get_event.return_value=bad
            with self.assertRaisesRegex(AuthorizedAuditReadError,"AUDIT_UNAVAILABLE"):
                self.service.get(AuditGetQuery(self.q.session_token,self.project,self.q.trace_id,self.view.audit_event_id))
        self.repo.get_event.return_value=None
        with self.assertRaisesRegex(AuthorizedAuditReadError,"RESOURCE_NOT_FOUND"):
            self.service.get(AuditGetQuery(self.q.session_token,self.project,self.q.trace_id,self.view.audit_event_id))

    def test_page_boundary_duplicates_order_and_next_position_rejected(self):
        older=replace(self.view,audit_event_id=uuid4(),occurred_at=self.now-timedelta(seconds=1))
        good=AuditPage((self.view,older),AuditPosition(older.occurred_at,older.audit_event_id),True)
        self.repo.list_events.return_value=good
        self.assertTrue(self.service.list(self.q).has_more)
        for bad in (AuditPage((older,self.view),good.next_position,True),AuditPage((self.view,self.view),good.next_position,True),
                    replace(good,next_position=AuditPosition(self.now,self.view.audit_event_id)),replace(good,has_more=False),
                    AuditPage((replace(self.view,occurred_at=self.search.end_at),),None,False)):
            self.repo.list_events.return_value=bad
            with self.assertRaisesRegex(AuthorizedAuditReadError,"AUDIT_UNAVAILABLE"):self.service.list(self.q)
        self.repo.list_events.return_value=AuditPage((self.view,),None,False)
        with self.assertRaisesRegex(AuthorizedAuditReadError,"AUDIT_UNAVAILABLE"):
            self.service.list(replace(self.q,search=replace(self.search,outcome="FAILED")))

    def test_token_shape_search_revalidation_repr_and_private_capability(self):
        self.assertNotIn(repr(self.q.session_token),repr(self.q))
        with self.assertRaisesRegex(AuthorizedAuditReadError,"VALIDATION_FAILED"):self.service.list(replace(self.q,session_token=b"short"))
        search=replace(self.search)
        object.__setattr__(search,"page_size",True)
        with self.assertRaisesRegex(AuthorizedAuditReadError,"VALIDATION_FAILED"):self.service.list(replace(self.q,search=search))
        principal=object();bound=_BoundAccess(self.tx,principal,self.project)
        self.assertTrue(bound.can_read_project(self.tx,principal,self.project))
        self.assertFalse(bound.can_read_project(object(),principal,self.project))
        self.assertFalse(bound.can_read_project(self.tx,object(),self.project))
        self.assertFalse(bound.can_read_deployment(self.tx,principal))
