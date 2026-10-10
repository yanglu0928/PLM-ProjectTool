"""Auth-owned explicit public metadata columns; caller transaction only."""
from sqlalchemy import select,tuple_
from .user_repository import _session
from .user_orm import UserRow
from ..application.user_read import UserReadView
from ..application.user_list import UserListPage


class SqlAlchemyUserReadRepository:
    def list(self,tx,*,page_size,before):
        query=select(UserRow.user_id,UserRow.username_display,UserRow.state,
            UserRow.deployment_role,UserRow.credential_version,UserRow.created_at,UserRow.updated_at,UserRow.lock_version)
        if before is not None:query=query.where(tuple_(UserRow.created_at,UserRow.user_id)<before)
        rows=_session(tx).execute(query.order_by(UserRow.created_at.desc(),UserRow.user_id.desc()).limit(page_size+1)).all()
        items=tuple(UserReadView(*row) for row in rows[:page_size])
        more=len(rows)>page_size
        return UserListPage(items,more,(items[-1].created_at,items[-1].user_id) if more else None)

    def get(self,tx,*,user_id):
        row=_session(tx).execute(select(UserRow.user_id,UserRow.username_display,UserRow.state,
            UserRow.deployment_role,UserRow.credential_version,UserRow.created_at,UserRow.updated_at,
            UserRow.lock_version).where(UserRow.user_id==user_id).with_for_update(read=True,of=UserRow)).one_or_none()
        return UserReadView(*row) if row is not None else None
