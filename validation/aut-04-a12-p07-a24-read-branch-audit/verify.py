"""Actual UserRead guard rejection trace and coverage coordinate evidence."""
import ast
import io
import json
import sys
import unittest
from contextlib import redirect_stdout, redirect_stderr
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import coverage

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION = ROOT / 'apps/backend/src/plm_assistant/modules/auth/application/user_read.py'
RUNTIME = ROOT / '.poc-runtime/auth-security-read-branch-audit'
CASES = ('test_bad_clock_or_clock_fault_never_reads_identity_or_target',
         'test_denied_current_admin_never_reads_target', 'test_missing_target_and_wrong_binding')


def main():
    previous = json.loads((ROOT / '.poc-runtime/auth-security-name-coverage/coverage.json').read_text(encoding='utf-8'))
    old_row = next(row for path, row in previous['files'].items() if Path(path).resolve() == PRODUCTION)
    missing = old_row['missing_branches']
    assert missing == [[62,72],[64,72],[66,72],[67,72],[69,72]], missing
    guards = {node.lineno: node for node in ast.walk(ast.parse(PRODUCTION.read_text(encoding='utf-8')))
              if isinstance(node, ast.If)}
    raised = {start: guards[start].body[0].lineno for start, _ in missing}
    assert all(isinstance(guards[start].body[0], ast.Raise) for start in raised)
    spec = spec_from_file_location('_existing_read_tests', ROOT / 'apps/backend/tests/unit/test_user_read.py')
    tests = module_from_spec(spec)
    spec.loader.exec_module(tests)
    class Audited(tests.UserReadTests):
        def tearDown(self):
            self.tx.commit.assert_not_called()
            assert self.uow.return_value.__exit__.call_count > 0
    def suite():
        return unittest.TestSuite(Audited(name) for name in CASES)
    diagnostics = io.StringIO()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    cov = coverage.Coverage(branch=True, source=[str(PRODUCTION.parent)], data_file=str(RUNTIME / '.coverage'))
    cov.start()
    with redirect_stdout(diagnostics), redirect_stderr(diagnostics):
        measured = unittest.TextTestRunner(stream=diagnostics, verbosity=0).run(suite())
    cov.stop()
    cov.save()
    assert measured.wasSuccessful() and measured.testsRun == 3
    cov.json_report(outfile=str(RUNTIME / 'coverage.json'))
    events = []
    def trace(frame, event, arg):
        if Path(frame.f_code.co_filename) == PRODUCTION and frame.f_code.co_name == 'get':
            if event in ('line', 'exception'):
                events.append((event, frame.f_lineno))
        return trace
    previous_trace = sys.gettrace()
    try:
        sys.settrace(trace)
        with redirect_stdout(diagnostics), redirect_stderr(diagnostics):
            traced = unittest.TextTestRunner(stream=diagnostics, verbosity=0).run(suite())
    finally:
        sys.settrace(previous_trace)
    assert traced.wasSuccessful() and traced.testsRun == 3
    payload = json.loads((RUNTIME / 'coverage.json').read_text(encoding='utf-8'))
    row = next(row for path, row in payload['files'].items() if Path(path).resolve() == PRODUCTION)
    actual = cov.get_data().arcs(str(PRODUCTION)) or []
    for start, destination in missing:
        count = events.count(('exception', raised[start]))
        assert count > 0, (start, 'No guard rejection observed')
        print('READ_BRANCH_AUDIT ' + json.dumps(dict(guard=start, raise_line=raised[start],
            exception_events=count, still_missing=[start,destination] in row['missing_branches'],
            recorded_arcs=[list(arc) for arc in actual if arc[0] == start]), sort_keys=True))
    print('PASS: three existing methods measured/traced independently, five actual guard refusals, noCommit/UOW exit. No production or full safety claim.')


if __name__ == '__main__':
    main()
