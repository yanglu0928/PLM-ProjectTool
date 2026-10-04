"""Coordinate-level actual rejection audit, no production or threshold edits."""
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
PRODUCTION = ROOT / 'apps/backend/src/plm_assistant/modules/auth/application/managed_user_create.py'
RUNTIME = ROOT / '.poc-runtime/auth-security-create-branch-audit'
CASES = ('test_malformed_receipts_refuse_before_result_or_hash',
         'test_replay_result_identity_and_proof_return_refuse_no_write',
         'test_write_source_identity_activation_and_first_coordinates_refuse',
         'test_username_conflict_fault_or_wrong_snapshot_safe')


def main():
    previous = json.loads((ROOT / '.poc-runtime/auth-security-name-coverage/coverage.json').read_text(encoding='utf-8'))
    row = next(row for path, row in previous['files'].items() if Path(path).resolve() == PRODUCTION)
    missing = row['missing_branches']
    assert missing == [[63,94],[65,94],[74,94],[75,94],[84,94],[88,94]], missing
    tree = ast.parse(PRODUCTION.read_text(encoding='utf-8'))
    guards = {node.lineno: node for node in ast.walk(tree) if isinstance(node, ast.If)}
    raise_lines = {start: guards[start].body[0].lineno for start, _ in missing}
    assert all(isinstance(guards[start].body[0], ast.Raise) for start in raise_lines)
    spec = spec_from_file_location('_actual_create_tests', ROOT / 'apps/backend/tests/unit/test_managed_user_create.py')
    tests = module_from_spec(spec)
    spec.loader.exec_module(tests)
    def suite():
        return unittest.TestSuite(tests.ManagedUserCreateTests(name) for name in CASES)
    diagnostics = io.StringIO()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    cov = coverage.Coverage(branch=True, source=[str(PRODUCTION.parent)], data_file=str(RUNTIME / '.coverage'))
    cov.start()
    with redirect_stdout(diagnostics), redirect_stderr(diagnostics):
        measured = unittest.TextTestRunner(stream=diagnostics, verbosity=0).run(suite())
    cov.stop()
    cov.save()
    assert measured.wasSuccessful() and measured.testsRun == 4
    cov.json_report(outfile=str(RUNTIME / 'coverage.json'))
    events = []
    def trace(frame, event, arg):
        if Path(frame.f_code.co_filename) == PRODUCTION and frame.f_code.co_name == 'create':
            if event in ('line', 'exception'):
                events.append((event, frame.f_lineno))
        return trace
    prior_trace = sys.gettrace()
    try:
        sys.settrace(trace)
        with redirect_stdout(diagnostics), redirect_stderr(diagnostics):
            traced = unittest.TextTestRunner(stream=diagnostics, verbosity=0).run(suite())
    finally:
        sys.settrace(prior_trace)
    assert traced.wasSuccessful() and traced.testsRun == 4
    actual = cov.get_data().arcs(str(PRODUCTION)) or []
    measured_json = json.loads((RUNTIME / 'coverage.json').read_text(encoding='utf-8'))
    current = next(row for path, row in measured_json['files'].items() if Path(path).resolve() == PRODUCTION)
    for start, destination in missing:
        count = events.count(('exception', raise_lines[start]))
        assert count > 0, (start, 'Existing tests did not execute guard rejection')
        print('CREATE_BRANCH_AUDIT ' + json.dumps(dict(guard=start, raise_line=raise_lines[start],
            exception_events=count, expected_missing=[start,destination],
            still_missing=[start,destination] in current['missing_branches'],
            recorded_arcs=[list(arc) for arc in actual if arc[0] == start]), sort_keys=True))
    print('PASS: four existing methods independently measured/traced; six guard rejection events proven. No production/threshold edits or full safety claim.')


if __name__ == '__main__':
    main()
