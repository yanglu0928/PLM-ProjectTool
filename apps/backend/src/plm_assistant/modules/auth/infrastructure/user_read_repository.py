"""Auth-owned explicit public metadata columns; caller transaction only."""
from sqlalchemy import select
from .user_repository import _session
from .user_orm import UserRow
from ..application.user_read import UserReadView


class SqlAlchemyUserReadRepository:
    def get(self,tx,*,user_id):
        row=_session(tx).execute(select(UserRow.user_id,UserRow.username_display,UserRow.state,
            UserRow.deployment_role,UserRow.credential_version,UserRow.created_at,UserRow.updated_at,
            UserRow.lock_version).where(UserRow.user_id==user_id).with_for_update(read=True,of=UserRow)).one_or_none()
        return UserReadView(*row) if row is not None else None
