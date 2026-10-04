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
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.audit.api.search_resolver import AuditCursorSearchResolver


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

    def test_resolver_after_current_authority_before_read_same_uow(self):
        def resolve(**kw):
            self.access.authenticated_user.assert_called_once()
            self.projects.require_in_transaction.assert_called_once()
            self.repo.list_events.assert_not_called()
            self.assertEqual(kw,dict(session_token=self.q.session_token,actor_id=self.actor,project_id=self.project,search=self.search))
            return self.search
        resolver=Mock();resolver.resolve.side_effect=resolve
        result=self.service.list_resolved(self.q,resolver)
        self.assertEqual(result.search,self.search)
        self.assertIs(self.repo.list_events.call_args.args[0],self.tx)
        self.tx.commit.assert_not_called()

    def test_resolver_never_called_when_authority_denied(self):
        resolver=Mock();self.access.authenticated_user.return_value=None
        with self.assertRaisesRegex(AuthorizedAuditReadError,"AUTH_ACCESS_DENIED"):
            self.service.list_resolved(self.q,resolver)
        resolver.resolve.assert_not_called();self.repo.list_events.assert_not_called()

    def test_malformed_cursor_only_safe_error_and_no_repository(self):
        resolver=AuditCursorSearchResolver(AuditListCursorCodec(b"k"*32),"bad")
        with self.assertRaisesRegex(AuthorizedAuditReadError,"REQUEST_MALFORMED"):
            self.service.list_resolved(self.q,resolver)
        self.repo.list_events.assert_not_called()

    def test_resolver_cannot_replace_filters_page_size_or_bad_position(self):
        for result in (None,replace(self.search,action="OTHER"),replace(self.search,page_size=1),
                       replace(self.search,after=AuditPosition(self.search.end_at,uuid4()))):
            resolver=Mock();resolver.resolve.return_value=result
            with self.assertRaisesRegex(AuthorizedAuditReadError,"AUDIT_UNAVAILABLE"):
                self.service.list_resolved(self.q,resolver)
        self.repo.list_events.assert_not_called()

    def test_signed_saved_window_is_effective_window_for_query_and_response(self):
        codec=AuditListCursorCodec(b"k"*32)
        position=AuditPosition(self.now,self.view.audit_event_id)
        token=codec.encode(session_token=self.q.session_token,actor_id=self.actor,project_id=self.project,search=self.search,position=position)
        moving=replace(self.search,start_at=self.search.start_at+timedelta(days=1),end_at=self.search.end_at+timedelta(days=1))
        self.repo.list_events.return_value=AuditPage((),None,False)
        result=self.service.list_resolved(replace(self.q,search=moving),AuditCursorSearchResolver(codec,token,dates_omitted=True))
        self.assertEqual(result.search,replace(self.search,after=position))
        self.assertEqual(self.repo.list_events.call_args.kwargs["search"],result.search)
        with self.assertRaisesRegex(AuthorizedAuditReadError,"REQUEST_MALFORMED"):
            self.service.list_resolved(replace(self.q,search=moving),AuditCursorSearchResolver(codec,token))

    def test_resolver_bad_input_and_unknown_error_fail_closed(self):
        for query in (None,replace(self.q,search=None),replace(self.q,search=replace(self.search,after=AuditPosition(self.now,uuid4())))):
            with self.assertRaisesRegex(AuthorizedAuditReadError,"VALIDATION_FAILED"):
                self.service.list_resolved(query,Mock())
        resolver=Mock();resolver.resolve.side_effect=ApplicationError("SYSTEM_INTERNAL")
        with self.assertRaisesRegex(AuthorizedAuditReadError,"AUDIT_UNAVAILABLE"):
            self.service.list_resolved(self.q,resolver)
        self.repo.list_events.assert_not_called()
