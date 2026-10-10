"""Actual Windows factory budget wiring; synthetic trust, isolated PostgreSQL."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import Mock, patch

from plm_assistant.entrypoints import production_login as prod
from plm_assistant.entrypoints.password_capacity import get_process_password_capacity

spec = spec_from_file_location('_capacity_windows', Path(__file__).resolve().parents[1] /
                              'aut-04-a12-p05-a07-windows-reset' / 'verify.py')
original = module_from_spec(spec)
spec.loader.exec_module(original)


def extra(v, settings):
    budget = get_process_password_capacity(slots=settings.password_kdf_slots)
    captured = {'reset': [], 'change': []}
    reset, change = prod.PasswordResetService, prod.PasswordChangeService

    def reset_service(**kwargs):
        assert kwargs['capacity'] is budget
        captured['reset'].append(kwargs['capacity'])
        return reset(**kwargs)

    def change_service(**kwargs):
        assert kwargs['capacity'] is budget
        captured['change'].append(kwargs['capacity'])
        return change(**kwargs)

    with patch.object(prod, 'PasswordResetService', side_effect=reset_service), \
         patch.object(prod, 'PasswordChangeService', side_effect=change_service):
        original.extra(v, settings)
    assert len(captured['reset']) >= 2 and len(captured['change']) >= 2
    assert budget.snapshot()['active'] == 0 and budget.snapshot()['peak'] <= settings.password_kdf_slots

    tables = ('auth_users', 'auth_password_credentials', 'auth_sessions', 'auth_user_create_results',
              'auth_user_state_results', 'auth_password_change_results', 'auth_password_reset_results',
              'aud_events', 'plt_idempotency_receipts')
    def snapshot():
        return {table: tuple(v['db'].execute(original.sql.SQL('SELECT * FROM plm.{} ORDER BY 1')
                          .format(original.sql.Identifier(table)))) for table in tables}
    before = snapshot()
    for value in (8 if settings.password_kdf_slots != 8 else 4, True, '4', 0, 17):
        built = []
        real = prod.create_database_runtime
        def tracked(url):
            runtime = real(url)
            runtime.dispose = Mock(wraps=runtime.dispose)
            built.append(runtime)
            return runtime
        with patch.object(prod, 'create_database_runtime', side_effect=tracked):
            try:
                prod.create_production_platform_write_app(settings.model_copy(update={'password_kdf_slots': value}))
            except prod.ProductionLoginStartupError:
                pass
            else:
                raise AssertionError('Invalid capacity returned a half-started application')
        assert len(built) == 1
        built[0].dispose.assert_called_once()
        assert snapshot() == before
    assert get_process_password_capacity(slots=settings.password_kdf_slots) is budget
    print('PASS actual Windows multiple write factories reset/change share one budget; '
          'conflicting and bypassed invalid configurations dispose once/no returned app/nine tables unchanged; '
          'original HTTP permission/reset/replay/change and mode/fault regressions passed. '
          'Mixed concurrent HTTP/performance and formal production trust remain unverified here.')


if __name__ == '__main__':
    original.windows.http.m.fixture.main(exercise=lambda v: original.windows.exercise(v, extra=extra))
