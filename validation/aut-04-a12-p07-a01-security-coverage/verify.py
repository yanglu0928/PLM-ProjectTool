"""Measured unit/contract coverage, not a claim of complete Auth security."""
import io
import json
import runpy
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import coverage

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'apps/backend/src/plm_assistant'
AUTH = SRC / 'modules/auth'
RUNTIME = ROOT / '.poc-runtime/auth-security-coverage'


def main(*, integrations=(), runtime=RUNTIME):
    runtime.mkdir(parents=True, exist_ok=True)
    cov = coverage.Coverage(branch=True, source=[str(AUTH), str(SRC / 'entrypoints')],
                            data_file=str(runtime / '.coverage'))
    cov.start()
    # Start coverage before discovery/import. Raw test diagnostics remain local,
    # not in committed evidence; report fixed counts if a test fails.
    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'apps/backend/tests'), pattern='test_*.py')
        result = unittest.TextTestRunner(stream=output, verbosity=0).run(suite)
    integration_results = []
    for folder in integrations:
        print('AUTH_SECURITY_INTEGRATION_START ' + folder, flush=True)
        with redirect_stdout(output), redirect_stderr(output):
            try:
                runpy.run_path(str(ROOT / 'validation' / folder / 'verify.py'), run_name='__main__')
            except Exception as exc:
                status = {'entrypoint': folder, 'passed': False, 'error_type': type(exc).__name__}
            else:
                status = {'entrypoint': folder, 'passed': True}
        integration_results.append(status)
        print('AUTH_SECURITY_INTEGRATION_RESULT ' + json.dumps(status, sort_keys=True), flush=True)
    cov.stop(); cov.save()
    cov.json_report(outfile=str(runtime / 'coverage.json'))
    payload = json.loads((runtime / 'coverage.json').read_text(encoding='utf-8'))
    files = payload['files']
    selected = []
    auth_rows = []
    for name, row in sorted(files.items()):
        path = Path(name).resolve()
        relative = path.relative_to(SRC).as_posix()
        if relative.startswith('modules/auth/'):
            auth_rows.append(row)
        password_related = (relative.startswith('modules/auth/') and path.name.startswith('password_')) or \
                           relative == 'modules/auth/infrastructure/scrypt_password.py' or \
                           relative == 'entrypoints/password_capacity.py'
        if password_related:
            selected.append({'file': relative, **row['summary'], 'missing_lines': row['missing_lines'],
                             'missing_branches': row.get('missing_branches', [])})
    assert selected and any(row['file'].endswith('password_reset_access.py') for row in selected)
    def totals(rows):
        keys = ('covered_lines', 'num_statements', 'covered_branches', 'num_branches')
        values = {key: sum(row['summary'][key] if 'summary' in row else row[key] for row in rows) for key in keys}
        values['line_percent'] = round(100 * values['covered_lines'] / values['num_statements'], 3)
        values['branch_percent'] = round(100 * values['covered_branches'] / values['num_branches'], 3)
        values['combined_percent'] = round(100 * (values['covered_lines'] + values['covered_branches']) /
                                         (values['num_statements'] + values['num_branches']), 3)
        values['threshold_90_pass'] = (10 * values['covered_lines'] >= 9 * values['num_statements'] and
                                      10 * values['covered_branches'] >= 9 * values['num_branches'])
        return values
    report = {'coverage_version': coverage.__version__, 'test_count': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
              'failed_test_ids': [test.id() for test, _ in result.failures + result.errors],
              'integrations': integration_results,
              'scope': 'full unit/contract plus declared integrations; password files plus scrypt/process budget; all Auth and Windows factory separate',
              'password_scope': totals(selected), 'all_auth_scope': totals(auth_rows), 'password_files': selected}
    factory = next(row['summary'] for name, row in files.items() if Path(name).name == 'production_login.py')
    report['windows_full_factory'] = factory
    print('AUTH_SECURITY_COVERAGE ' + json.dumps({key: value for key, value in report.items()
                                                 if key != 'password_files'}, sort_keys=True))
    for row in selected:
        print('AUTH_SECURITY_COVERAGE_FILE ' + json.dumps({key: row[key] for key in
            ('file', 'covered_lines', 'num_statements', 'covered_branches', 'num_branches', 'missing_lines', 'missing_branches')}, sort_keys=True))
    if not result.wasSuccessful() or any(not row['passed'] for row in integration_results) or not report['password_scope']['threshold_90_pass']:
        raise SystemExit('AUTH_SECURITY_COVERAGE INCOMPLETE: tests/90% line and branch evidence required; no Gate closure')


if __name__ == '__main__':
    main()
