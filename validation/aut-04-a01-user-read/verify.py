"""Actual current Admin sessions and safe user columns in isolated PostgreSQL."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from dataclasses import replace
from psycopg import sql
from plm_assistant.modules.auth.application.user_read import AuthorizedUserReadService,UserGetQuery,UserReadError
from plm_assistant.modules.auth.infrastructure.user_read_repository import SqlAlchemyUserReadRepository
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess

spec=spec_from_file_location('_user_read_actual',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)

def exercise(v):
    db=v['db'];tables=('auth_users','auth_password_credentials','auth_sessions','aud_events','plt_idempotency_receipts')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    service=AuthorizedUserReadService(unit_of_work=v['uow'],access=SqlAlchemyDeploymentReadAccess(),
        repository=SqlAlchemyUserReadRepository(),license_guard=v['guard'])
    q=UserGetQuery(v['tokens'][1],v['users'][0],uuid4())
    before=snapshot();view=service.get(q)
    assert view.user_id==v['users'][0] and view.account_state=='ENABLED' and view.deployment_role=='NONE'
    assert snapshot()==before
    def reject(query,code):
        before=snapshot()
        try:service.get(query)
        except UserReadError as exc:assert exc.code==code,(exc.code,code)
        else:raise AssertionError('Unauthorized User metadata returned')
        assert snapshot()==before
    reject(replace(q,session_token=v['tokens'][0]),'AUTH_ACCESS_DENIED')
    reject(replace(q,session_token=b'?'*32),'AUTH_ACCESS_DENIED')
    reject(replace(q,user_id=uuid4()),'RESOURCE_NOT_FOUND')
    revoked_token=b'r'*32
    revoked_admin=fixture.base.auth.user(db,'Synthetic revoked user read',revoked_token,'DEPLOYMENT_ADMIN')
    db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='ADMIN_REVOKED',lock_version=lock_version+1 WHERE user_id=%s",(revoked_admin,))
    reject(replace(q,session_token=revoked_token),'AUTH_ACCESS_DENIED')
    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s",(q.user_id,))
    try:
        before=snapshot();assert service.get(q).account_state=='DISABLED';assert snapshot()==before
    finally:db.execute("UPDATE plm.auth_users SET state='ENABLED' WHERE user_id=%s",(q.user_id,))
    db.execute("UPDATE plm.auth_users SET deployment_role='NONE' WHERE user_id=%s",(v['users'][1],))
    try:reject(q,'AUTH_ACCESS_DENIED')
    finally:db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s",(v['users'][1],))
    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s",(v['users'][1],))
    try:reject(q,'AUTH_ACCESS_DENIED')
    finally:db.execute("UPDATE plm.auth_users SET state='ENABLED' WHERE user_id=%s",(v['users'][1],))
    v['guard'].enabled=False
    try:reject(q,'LICENSE_OPERATION_DENIED')
    finally:v['guard'].enabled=True
    print('User detail internal PASS: actual current Session/Admin, ordinary/unknown/revoked Session, unknown target, revoked Admin role/disabled Admin/License reject, disabled target visible, five complete tables unchanged. Only explicit metadata/no Credential table query. Positive License synthetic; HTTP/list/management writes/performance/production/Gate pending.')

if __name__=='__main__':fixture.main(exercise=exercise)
