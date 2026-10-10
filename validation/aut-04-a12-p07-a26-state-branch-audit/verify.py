"""Five actual UserState rejection coordinates; one new source-type contract."""
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
PRODUCTION = ROOT / 'apps/backend/src/plm_assistant/modules/auth/application/user_state.py'
RUNTIME = ROOT / '.poc-runtime/auth-security-state-branch-audit'
CASES = ('test_actor_proof_wrong_user_view_refuses_before_reservation',
         'test_bad_dependency_or_lock_is_static', 'test_receipt_type_status_and_result_reference_refuse_no_write',
         'test_change_response_contract_refuses_before_audit', 'test_first_response_binding_and_invalid_audit_refuse_before_complete')


def main():
    previous = json.loads((ROOT / '.poc-runtime/auth-security-name-coverage/coverage.json').read_text(encoding='utf-8'))
    row = next(row for path, row in previous['files'].items() if Path(path).resolve() == PRODUCTION)
    missing = row['missing_branches']
    assert missing == [[42,50],[101,139],[111,139],[116,139],[127,139]], missing
    guards = {node.lineno: node for node in ast.walk(ast.parse(PRODUCTION.read_text(encoding='utf-8')))
              if isinstance(node, ast.If)}
    raised = {start: guards[start].body[0].lineno for start, _ in missing}
    assert all(isinstance(guards[start].body[0], ast.Raise) for start in raised)
    spec = spec_from_file_location('_state_guard_tests', ROOT / 'apps/backend/tests/unit/test_user_state_service.py')
    tests = module_from_spec(spec)
    spec.loader.exec_module(tests)
    def suite():
        return unittest.TestSuite(tests.UserStateServiceTests(name) for name in CASES)
    diagnostics = io.StringIO()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    cov = coverage.Coverage(branch=True, source=[str(PRODUCTION.parent)], data_file=str(RUNTIME / '.coverage'))
    cov.start()
    with redirect_stdout(diagnostics), redirect_stderr(diagnostics):
        measured = unittest.TextTestRunner(stream=diagnostics, verbosity=0).run(suite())
    cov.stop()
    cov.save()
    assert measured.wasSuccessful() and measured.testsRun == 5
    cov.json_report(outfile=str(RUNTIME / 'coverage.json'))
    events = []
    def trace(frame, event, arg):
        if Path(frame.f_code.co_filename) == PRODUCTION and frame.f_code.co_name in ('_execute', '__post_init__'):
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
    assert traced.wasSuccessful() and traced.testsRun == 5
    payload = json.loads((RUNTIME / 'coverage.json').read_text(encoding='utf-8'))
    current = next(row for path, row in payload['files'].items() if Path(path).resolve() == PRODUCTION)
    arcs = cov.get_data().arcs(str(PRODUCTION)) or []
    for start, end in missing:
        count = events.count(('exception', raised[start]))
        assert count > 0, (start, 'Guard did not reject')
        print('STATE_BRANCH_AUDIT ' + json.dumps(dict(guard=start, raise_line=raised[start], exception_events=count,
            still_missing=[start,end] in current['missing_branches'],
            recorded_arcs=[list(arc) for arc in arcs if arc[0] == start]), sort_keys=True))
    print('PASS: five methods measured/traced; ActorProof wrong user view is a new behavior test, no production edits or full safety claim.')


if __name__ == '__main__':
    main()
