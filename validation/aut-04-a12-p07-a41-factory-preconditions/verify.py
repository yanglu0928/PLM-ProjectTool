"""Full tests and actual Windows login chain, factory coverage separate from Auth."""
import io
import json
import runpy
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import coverage

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / '.poc-runtime/auth-security-factory-preconditions'


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    cov = coverage.Coverage(branch=True, source=[str(ROOT / 'apps/backend/src/plm_assistant/entrypoints')],
                            data_file=str(RUNTIME / '.coverage'))
    cov.start()
    diagnostics = io.StringIO()
    with redirect_stdout(diagnostics), redirect_stderr(diagnostics):
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'apps/backend/tests'), pattern='test_*.py')
        result = unittest.TextTestRunner(stream=diagnostics, verbosity=0).run(suite)
        runpy.run_path(str(ROOT / 'validation/aut-03-a07-p03-production-login/verify.py'), run_name='__main__')
    cov.stop()
    cov.save()
    assert result.wasSuccessful()
    cov.json_report(outfile=str(RUNTIME / 'coverage.json'))
    payload = json.loads((RUNTIME / 'coverage.json').read_text(encoding='utf-8'))
    row = next(row for path,row in payload['files'].items() if Path(path).name == 'production_login.py')
    passed = (10*row['summary']['covered_lines'] >= 9*row['summary']['num_statements'] and
              10*row['summary']['covered_branches'] >= 9*row['summary']['num_branches'])
    print('FACTORY_PRECONDITION_RESULT ' + json.dumps(dict(test_count=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        actual_windows_login_chain=True, file_summary=row['summary'], threshold_90_pass=passed,
        missing_lines=row['missing_lines'], missing_branches=row['missing_branches']), sort_keys=True))
    assert passed
    print('PASS: factory measured separately, no production trust, TLS/service/performance or Gate claim.')


if __name__ == '__main__':
    main()
