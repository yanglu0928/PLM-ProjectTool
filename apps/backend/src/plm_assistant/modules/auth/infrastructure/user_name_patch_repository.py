"""Name-only conditional UPDATE; current and initial credential sources untouched."""
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from .user_repository import _session
from .user_orm import UserRow
from ..application.user_read import UserReadView, _id
from ..application.user_name_patch import UserNamePatchError
from ..domain.username import normalize_username, CanonicalUsername

_COLUMNS = (UserRow.user_id, UserRow.username_display, UserRow.state,
    UserRow.deployment_role, UserRow.credential_version, UserRow.created_at,
    UserRow.updated_at, UserRow.lock_version)


class SqlAlchemyUserNamePatchRepository:
    def patch(self, tx, *, user_id, expected_version, username, actor_id):
        if (not _id(user_id) or not _id(actor_id) or type(expected_version) is not int
            or not 0 <= expected_version <= 9223372036854775807
            or type(username) is not CanonicalUsername
            or normalize_username(username.display) != username):
            raise UserNamePatchError('VALIDATION_FAILED')
        session = _session(tx)
        row = session.execute(select(*_COLUMNS, UserRow.username_normalized).where(
            UserRow.user_id == user_id).with_for_update(of=UserRow)).one_or_none()
        if row is None:
            raise UserNamePatchError('RESOURCE_NOT_FOUND')
        before = UserReadView(*row[:8])
        original = normalize_username(before.username_display)
        if original.display != before.username_display or original.normalized != row[8]:
            raise UserNamePatchError()
        if before.lock_version != expected_version:
            raise UserNamePatchError('CONFLICT_VERSION')
        if username == original:
            return before, False
        if expected_version == 9223372036854775807:
            raise UserNamePatchError('CONFLICT_VERSION')
        try:
            result = session.execute(update(UserRow).where(UserRow.user_id == user_id,
                UserRow.lock_version == expected_version).values(
                username_display=username.display, username_normalized=username.normalized,
                updated_by=actor_id, updated_at=func.statement_timestamp(),
                lock_version=UserRow.lock_version + 1).returning(*_COLUMNS)).one_or_none()
        except IntegrityError as exc:
            if (getattr(exc.orig, 'sqlstate', None) == '23505'
                and getattr(getattr(exc.orig, 'diag', None), 'constraint_name', None)
                == 'uq_auth_users__username_norm'):
                raise UserNamePatchError('CONFLICT_DUPLICATE') from None
            raise
        if result is None:
            raise UserNamePatchError('CONFLICT_VERSION')
        after = UserReadView(*result)
        if (after.updated_at < before.updated_at
            or any(getattr(after, key) != getattr(before, key) for key in
                   ('user_id', 'account_state', 'deployment_role', 'credential_version', 'created_at'))):
            raise UserNamePatchError()
        return after, True
