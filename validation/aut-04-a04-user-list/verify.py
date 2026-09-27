"""Current real Admin metadata pagination, UUID tie order and revocation."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from dataclasses import replace
from uuid import uuid4
from psycopg import sql
from plm_assistant.modules.auth.application.user_list import AuthorizedUserListService,UserListQuery
from plm_assistant.modules.auth.application.user_read import UserReadError
from plm_assistant.modules.auth.infrastructure.user_read_repository import SqlAlchemyUserReadRepository
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess

spec=spec_from_file_location('_user_list_actual',Path(__file__).resolve().parents[1]/'aut-04-a01-user-read'/'verify.py')
internal=module_from_spec(spec);spec.loader.exec_module(internal)

def exercise(v):
    internal.exercise(v)
    db=v['db'];ties=[]
    for i in range(7):ties.append(internal.fixture.base.auth.user(db,f'Synthetic tie user {i}',bytes([30+i])*32,'NONE'))
    db.execute("UPDATE plm.auth_users SET created_at=statement_timestamp()-interval '1 hour' WHERE user_id=ANY(%s)",(ties,))
    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s",(ties[0],))
    service=AuthorizedUserListService(unit_of_work=v['uow'],access=SqlAlchemyDeploymentReadAccess(),
        repository=SqlAlchemyUserReadRepository(),license_guard=v['guard'])
    tables=('auth_users','auth_password_credentials','auth_sessions','aud_events','plt_idempotency_receipts')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    q=UserListQuery(v['tokens'][1],uuid4(),2)
    expected=[row[0] for row in db.execute('SELECT user_id FROM plm.auth_users ORDER BY created_at DESC,user_id DESC')]
    seen=[];positions=set();before=snapshot()
    while True:
        page=service.list(q);assert snapshot()==before
        seen.extend(item.user_id for item in page.items)
        assert all(set(item.__dataclass_fields__)=={'user_id','username_display','account_state','deployment_role',
            'credential_version','created_at','updated_at','lock_version'} for item in page.items)
        if not page.has_more:
            assert page.next_position is None;break
        assert page.next_position not in positions;positions.add(page.next_position);assert len(positions)<20
        q=replace(q,before=page.next_position)
    assert seen==expected and len(seen)==len(set(seen))
    assert [i for i in seen if i in ties]==sorted(ties,reverse=True)
    empty=service.list(replace(q,before=(page.items[-1].created_at,page.items[-1].user_id)))
    assert empty.items==() and not empty.has_more and snapshot()==before
    full=service.list(UserListQuery(v['tokens'][1],uuid4(),200))
    assert not full.has_more and any(item.user_id==ties[0] and item.account_state=='DISABLED' for item in full.items)
    def reject(query,code):
        before=snapshot()
        try:service.list(query)
        except UserReadError as exc:assert exc.code==code,(exc.code,code)
        else:raise AssertionError('Unsafe User page returned')
        assert snapshot()==before
    for token in (v['tokens'][0],b'?'*32,b'r'*32):reject(replace(q,session_token=token),'AUTH_ACCESS_DENIED')
    db.execute("UPDATE plm.auth_users SET deployment_role='NONE' WHERE user_id=%s",(v['users'][1],))
    try:reject(q,'AUTH_ACCESS_DENIED')
    finally:db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s",(v['users'][1],))
    v['guard'].enabled=False
    try:reject(q,'LICENSE_OPERATION_DENIED')
    finally:v['guard'].enabled=True
    print('User list internal PASS: actual current Admin/Session, seven same-timestamp UUID ties, multi-page exact stable order/no duplicates, empty final page/disabled target visible; ordinary/unknown/revoked Session and revoked role/License reject five complete tables unchanged. No Credential columns/query or writes. Positive License synthetic; opaque cursor/HTTP/Windows/performance/full management/Gate/package pending.')

if __name__=='__main__':internal.fixture.main(exercise=exercise)
