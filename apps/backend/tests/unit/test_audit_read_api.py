from dataclasses import replace
from datetime import datetime,timezone,timedelta
from unittest.mock import Mock
from uuid import uuid4
import unittest
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.audit.api.read_events import create_audit_read_router
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.audit.application.authorized_read import AuthorizedAuditListContext,AuthorizedAuditReadError
from plm_assistant.modules.audit.application.queries.audit_query import AuditPage,AuditPosition,AuditEventView


class AuditReadApiTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc);self.project,self.actor=uuid4(),uuid4()
        self.view=AuditEventView(uuid4(),self.now-timedelta(seconds=1),uuid4(),"PROJECT",self.project,"USER",self.actor,None,
            "SYNTHETIC_READ","SUCCESS",None,None,None,None,None,None,None)
        self.reads=Mock();self.codec=AuditListCursorCodec(b"k"*32)
        self.reads.list_resolved.side_effect=lambda q,r:AuthorizedAuditListContext(self.actor,q.project_id,AuditPage((self.view,),None,False),r.resolve(session_token=q.session_token,actor_id=self.actor,project_id=q.project_id,search=q.search))
        self.reads.get.return_value=self.view
        self.client=TestClient(create_app(audit_read_router=create_audit_read_router(reads=self.reads,origins=LoginOriginPolicy(["http://localhost"]),cursors=self.codec,clock=lambda:self.now)),base_url="http://localhost")
        self.cookie={"Cookie":"plm_session="+(b"s"*32).hex()}
        self.path=f"/api/v1/projects/{self.project}/audit-events"

    def get(self,path=None,**kwargs):return self.client.get(path or self.path,headers=self.cookie,**kwargs)

    def test_list_and_detail_safe_projection_trace_no_store(self):
        response=self.get();self.assertEqual(response.status_code,200)
        data=response.json()["data"];self.assertFalse(data["has_more"]);self.assertIsNone(data["next_cursor"])
        self.assertEqual(data["items"][0]["actor"]["user_id"],str(self.actor))
        self.assertEqual(response.headers["Cache-Control"],"no-store")
        self.assertIn("trace_id",response.json())
        self.assertEqual(self.get(self.path+"/"+str(self.view.audit_event_id)).status_code,200)
        self.assertNotIn("actor_hint_digest",response.text);self.assertNotIn("session",response.text)

    def test_unknown_duplicate_invalid_filters_dates_and_sizes(self):
        for query,status in (("extra=x",400),("page_size=2&page_size=2",400),("page_size=0",422),("page_size=201",422),
            ("start_at=2026-09-01T00:00:00Z",422),("start_at=2026-09-01&end_at=2026-09-02",422),
            ("start_at=2026-01-01T00:00:00Z&end_at=2026-09-01T00:00:00Z",422),
            ("actor_id=00000000-0000-0000-0000-000000000000",422),("action=private text",422),("outcome=OTHER",422)):
            self.assertEqual(self.get(self.path+"?"+query).status_code,status,query)
        self.reads.list_resolved.assert_not_called()

    def test_cookie_host_and_unmounted_default(self):
        self.assertEqual(self.client.get(self.path).status_code,401)
        self.assertEqual(self.client.get(self.path,headers=self.cookie|{"Host":"evil.test"}).status_code,403)
        self.assertEqual(TestClient(create_app()).get(self.path).status_code,404)
        self.reads.list_resolved.assert_not_called()

    def test_error_mapping_and_no_detail_filters_or_writes(self):
        for code,status in (("RESOURCE_NOT_FOUND",404),("LICENSE_OPERATION_DENIED",403),("AUTH_ACCESS_DENIED",401),("REQUEST_MALFORMED",400),("AUDIT_UNAVAILABLE",503)):
            self.reads.list_resolved.side_effect=AuthorizedAuditReadError(code)
            self.assertEqual(self.get().status_code,status)
        self.assertEqual(self.get(self.path+"/"+str(self.view.audit_event_id)+"?page_size=1").status_code,400)
        self.assertEqual(self.client.post(self.path,headers=self.cookie).status_code,405)

    def test_actual_cursor_roundtrip_default_window_and_explicit_date_reject(self):
        older=replace(self.view,audit_event_id=uuid4(),occurred_at=self.view.occurred_at-timedelta(seconds=1))
        def pages(q,r):
            search=r.resolve(session_token=q.session_token,actor_id=self.actor,project_id=q.project_id,search=q.search)
            if search.after is None:page=AuditPage((self.view,),AuditPosition(self.view.occurred_at,self.view.audit_event_id),True)
            else:page=AuditPage((older,),None,False)
            return AuthorizedAuditListContext(self.actor,q.project_id,page,search)
        self.reads.list_resolved.side_effect=pages
        first=self.get(params={"page_size":"1"});self.assertEqual(first.status_code,200)
        cursor=first.json()["data"]["next_cursor"]
        second=self.get(params={"page_size":"1","cursor":cursor});self.assertEqual(second.status_code,200)
        self.assertEqual(second.json()["data"]["items"][0]["audit_event_id"],str(older.audit_event_id))
        self.assertEqual(self.get(params={"page_size":"2","cursor":cursor}).status_code,400)
        self.assertEqual(self.get(params={"page_size":"1","cursor":cursor,"start_at":(self.now-timedelta(hours=12)).isoformat(),"end_at":self.now.isoformat()}).status_code,400)

    def test_deployment_scope_and_bad_source_fail_closed(self):
        self.view=replace(self.view,event_scope="DEPLOYMENT",target_project_id=None)
        self.reads.get.return_value=self.view
        self.assertEqual(self.get("/api/v1/admin/audit-events").status_code,200)
        self.assertEqual(self.get("/api/v1/admin/audit-events/"+str(self.view.audit_event_id)).status_code,200)
        self.assertEqual(self.get().status_code,503)
        self.reads.get.return_value=replace(self.view,reason_code="private text")
        self.assertEqual(self.get("/api/v1/admin/audit-events/"+str(self.view.audit_event_id)).status_code,503)


if __name__=="__main__":unittest.main()
