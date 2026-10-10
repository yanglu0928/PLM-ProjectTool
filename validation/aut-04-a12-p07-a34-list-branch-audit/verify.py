"""Actual UserList refusal traces and three coverage coordinates."""
import ast
import importlib
import io
import json
import sys
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import coverage

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION = ROOT / 'apps/backend/src/plm_assistant/modules/auth/application/user_list.py'
RUNTIME = ROOT / '.poc-runtime/auth-security-list-branch-audit'
CASES = ('test_invalid_clock_or_clock_fault_refuses_before_identity_and_page',
         'test_no_admin_never_reads_page', 'test_repo_boundary_and_page_size_binding')


def main():
    previous = json.loads((ROOT / '.poc-runtime/auth-security-source-coverage/coverage.json').read_text(encoding='utf-8'))
    row = next(row for path,row in previous['files'].items() if Path(path).resolve() == PRODUCTION)
    missing = [arc for arc in row['missing_branches'] if arc[1] == 68]
    assert missing == [[57,68],[59,68],[61,68]], missing
    guards = {node.lineno:node for node in ast.walk(ast.parse(PRODUCTION.read_text(encoding='utf-8')))
              if isinstance(node,ast.If)}
    raised = {start:guards[start].body[0].lineno for start,_ in missing}
    assert all(isinstance(guards[start].body[0],ast.Raise) for start in raised)
    sys.path.insert(0,str(ROOT / 'apps/backend/tests'))
    tests = importlib.import_module('unit.test_user_list')
    class Audited(tests.UserListTests):
        def tearDown(self):
            self.tx.commit.assert_not_called()
            assert self.uow.return_value.__exit__.call_count > 0
    def suite():
        return unittest.TestSuite(Audited(name) for name in CASES)
    diagnostics = io.StringIO()
    RUNTIME.mkdir(parents=True,exist_ok=True)
    cov = coverage.Coverage(branch=True,source=[str(PRODUCTION.parent)],data_file=str(RUNTIME / '.coverage'))
    cov.start()
    with redirect_stdout(diagnostics),redirect_stderr(diagnostics):
        measured = unittest.TextTestRunner(stream=diagnostics,verbosity=0).run(suite())
    cov.stop()
    cov.save()
    assert measured.wasSuccessful() and measured.testsRun == 3
    cov.json_report(outfile=str(RUNTIME / 'coverage.json'))
    events = []
    def trace(frame,event,arg):
        if Path(frame.f_code.co_filename) == PRODUCTION and frame.f_code.co_name == 'list':
            if event in ('line','exception'):
                events.append((event,frame.f_lineno))
        return trace
    prior = sys.gettrace()
    try:
        sys.settrace(trace)
        with redirect_stdout(diagnostics),redirect_stderr(diagnostics):
            traced = unittest.TextTestRunner(stream=diagnostics,verbosity=0).run(suite())
    finally:
        sys.settrace(prior)
    assert traced.wasSuccessful() and traced.testsRun == 3
    payload = json.loads((RUNTIME / 'coverage.json').read_text(encoding='utf-8'))
    current = next(row for path,row in payload['files'].items() if Path(path).resolve() == PRODUCTION)
    arcs = cov.get_data().arcs(str(PRODUCTION)) or []
    for start,end in missing:
        count = events.count(('exception',raised[start]))
        assert count > 0,(start,'Rejection not observed')
        print('LIST_BRANCH_AUDIT ' + json.dumps(dict(guard=start,raise_line=raised[start],exception_events=count,
            still_missing=[start,end] in current['missing_branches'],
            recorded_arcs=[list(arc) for arc in arcs if arc[0] == start]),sort_keys=True))
    print('PASS: three methods independently measured/traced, actual refusals and noCommit/UOW exit. No production or full safety claim.')


if __name__ == '__main__':
    main()
