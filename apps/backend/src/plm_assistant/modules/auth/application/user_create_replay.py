"""Consumes an exact original-password proof; never grants User-create authority."""
from dataclasses import dataclass, field
from .user_create_result import UserCreateResult


class UserCreateReplayError(RuntimeError):
    def __init__(self, code='AUTH_CREATE_REPLAY_UNAVAILABLE'):
        self.code=code if type(code) is str and code in (
            'AUTH_CREATE_REPLAY_UNAVAILABLE','VALIDATION_FAILED','CONFLICT_IDEMPOTENCY'
        ) else 'AUTH_CREATE_REPLAY_UNAVAILABLE'
        super().__init__(self.code)


@dataclass(slots=True)
class UserCreatePasswordProof:
    password: bytearray = field(repr=False)

    def erase(self):
        if type(self.password) is bytearray:
            self.password[:] = b'\x00' * len(self.password)


class UserCreateReplayVerifier:
    def __init__(self, *, source):
        if source is None:
            raise ValueError('Actual original credential source required')
        self._source=source

    def require_match(self, transaction, *, result, proof):
        try:
            if type(result) is not UserCreateResult or type(proof) is not UserCreatePasswordProof:
                raise UserCreateReplayError('VALIDATION_FAILED')
            result.__post_init__()
            secret=proof.password
            if type(secret) is not bytearray or not 1<=len(secret)<=1024 or b'\x00' in secret:
                raise UserCreateReplayError('VALIDATION_FAILED')
            try: secret.decode('utf-8', errors='strict')
            except UnicodeDecodeError: raise UserCreateReplayError('VALIDATION_FAILED') from None
            view=memoryview(secret)
            try:
                matched=self._source.verify_initial_password(transaction,result=result,password=view)
            finally: view.release()
            if matched is False: raise UserCreateReplayError('CONFLICT_IDEMPOTENCY')
            if matched is not True: raise UserCreateReplayError()
            return result
        except UserCreateReplayError: raise
        except Exception: raise UserCreateReplayError() from None
        finally:
            if type(proof) is UserCreatePasswordProof:
                proof.erase()
