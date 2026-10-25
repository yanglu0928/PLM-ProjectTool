import unittest
from types import SimpleNamespace
from datetime import datetime, timezone
from uuid import uuid4
from dataclasses import replace
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult
from plm_assistant.modules.auth.application.password_reset_result import PasswordResetResult
from plm_assistant.modules.auth.application.password_change_result import PasswordChangeResult
from plm_assistant.modules.auth.application.password_reset_replay import PasswordResetReplayError
from plm_assistant.modules.auth.application.password_change_replay import PasswordChangeReplayError
from plm_assistant.modules.auth.infrastructure.password_reset_result_repository import SqlAlchemyPasswordResetResults
from plm_assistant.modules.auth.infrastructure.password_change_result_repository import SqlAlchemyPasswordChangeResults
from plm_assistant.modules.auth.infrastructure.scrypt_password import PARAMETERS


class HistoricalSourceTests(unittest.TestCase):
    def cases(self):
        now = datetime.now(timezone.utc)
        reset = PasswordResetResult(uuid4(),uuid4(),uuid4(),uuid4(),uuid4(),1,2,1,2,'ENABLED',uuid4(),uuid4(),1,now,now)
        change = PasswordChangeResult(uuid4(),uuid4(),uuid4(),uuid4(),1,2,1,2,uuid4(),uuid4(),1,now,now)
        yield SqlAlchemyPasswordResetResults, PasswordResetReplayError, reset, {}
        for role in ('BEFORE','AFTER'):
            yield SqlAlchemyPasswordChangeResults, PasswordChangeReplayError, change, {'role': role}

    def source(self):
        return PasswordHashResult('$scrypt$1$131072$8$1$'+'a'*32+'$'+'b'*64, 'SCRYPT', dict(PARAMETERS))

    def test_copy_hidden_and_fresh_recheck_no_kdf(self):
        for cls, error, result, role in self.cases():
            repo = cls(verifier=object())
            original = self.source()
            repo.get = lambda *a, **k: result
            repo._credential = lambda *a, **k: original
            source = repo.password_source(None, result=result, **role)
            self.assertEqual(source, original)
            self.assertIsNot(source.parameter_set, original.parameter_set)
            self.assertNotIn(original.password_hash, repr(source))
            self.assertIsNone(repo.require_password_source(None, result=result, source=source, **role))
            other = replace(source, password_hash=source.password_hash[:-1]+'c')
            with self.assertRaises(error):
                repo.require_password_source(None, result=result, source=other, **role)
            repo.get = lambda *a, **k: None
            with self.assertRaises(error):
                repo.password_source(None, result=result, **role)

    def test_detached_verifier_strict_bool_and_static_errors(self):
        for cls, error, result, role in self.cases():
            for value in (True, False, 1, None, RuntimeError('synthetic private driver')):
                def verify(*args, **kwargs):
                    if isinstance(value, Exception): raise value
                    return value
                repo = cls(verifier=SimpleNamespace(verify_password=verify))
                with memoryview(b'synthetic') as password:
                    if type(value) is bool:
                        self.assertIs(repo.verify_password_source(source=self.source(), password=password), value)
                    else:
                        with self.assertRaises(error) as caught:
                            repo.verify_password_source(source=self.source(), password=password)
                        self.assertNotIn('private', str(caught.exception))

    def test_bad_source_profile_password_and_result_fail_closed(self):
        for cls, error, result, role in self.cases():
            repo = cls(verifier=object())
            for source in (None, object(), replace(self.source(), algorithm_id='other'),
                           replace(self.source(), parameter_set={'n':1})):
                with self.assertRaises(error):
                    repo.verify_password_source(source=source, password=memoryview(b'x'))
            for password in (b'x', memoryview(b''), memoryview(b'x'*1025)):
                with self.assertRaises(error):
                    repo.verify_password_source(source=self.source(), password=password)
            with self.assertRaises(error): repo.password_source(None, result=object(), **role)

    def test_original_verify_delegates_exact_source(self):
        for cls, error, result, role in self.cases():
            repo = cls(verifier=object()); calls=[]; source=self.source()
            def read(tx, **kwargs):
                calls.append((tx, kwargs)); return source
            repo.password_source=read
            repo.verify_password_source=lambda **kwargs: kwargs['source'] is source
            with memoryview(b'x') as password:
                method=repo.verify_credential_password if role else repo.verify_reset_password
                self.assertTrue(method('tx', result=result, password=password, **role))
            self.assertEqual(calls,[('tx', {'result':result, **role})])
