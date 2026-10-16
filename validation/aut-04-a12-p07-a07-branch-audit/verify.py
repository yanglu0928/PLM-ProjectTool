"""Compare actual rejection trace with coverage arcs, without gate exemptions."""
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
HERE = Path(__file__).resolve().parent
PRODUCTION = ROOT / 'apps/backend/src/plm_assistant/modules/auth/application/password_change.py'


def load(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    target = ast.parse(PRODUCTION.read_text(encoding='utf-8'))
    service = next(node for node in target.body if isinstance(node, ast.ClassDef) and node.name == 'PasswordChangeService')
    method = next(node for node in service.body if isinstance(node, ast.FunctionDef) and node.name == '_change')
    guard = next(node for node in ast.walk(method) if isinstance(node, ast.If) and
                 isinstance(node.test, ast.Compare) and ast.unparse(node.test) == 'type(source) is not PasswordHashResult')
    guard_line, raise_line = guard.lineno, guard.body[0].lineno
    # Keep the original compact-source evidence intact when validating the expanded source.
    RUNTIME = ROOT / ('.poc-runtime/auth-security-branch-audit' if guard_line == raise_line
                      else '.poc-runtime/auth-security-branch-audit-expanded')
    RUNTIME.mkdir(parents=True, exist_ok=True)
    tree = ast.parse((HERE / 'fixture.py').read_text(encoding='utf-8'))
    compact, expanded = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    # Function names and line locations differ, but actual bodies must be identical.
    assert ast.dump(ast.Module(body=compact.body, type_ignores=[])) == ast.dump(
        ast.Module(body=expanded.body, type_ignores=[]))
    guards = [node.body[0].body[0].lineno for node in (compact, expanded)]
    cov = coverage.Coverage(branch=True, source=[str(HERE)], data_file=str(RUNTIME / '.coverage-fixture'))
    cov.start()
    fixture = load('_branch_layout_fixture', HERE / 'fixture.py')
    for reject, expected in ((False, 'accepted'), (True, 'denied')):
        assert fixture.compact(reject) == fixture.expanded(reject) == expected
    cov.stop(); cov.save()
    cov.json_report(outfile=str(RUNTIME / 'fixture-coverage.json'))
    payload = json.loads((RUNTIME / 'fixture-coverage.json').read_text(encoding='utf-8'))
    row = next(row for name, row in payload['files'].items() if Path(name).name == 'fixture.py')
    layout = {name: [arc for arc in row['missing_branches'] if arc[0] == line]
              for name, line in zip(('compact', 'expanded'), guards)}

    retry_tree = ast.parse((HERE / 'retry_fixture.py').read_text(encoding='utf-8'))
    retry_nodes = [node for node in retry_tree.body if isinstance(node, ast.FunctionDef)]
    # Normalize self-call names only; statements and exception/cleanup structure stay equal.
    for node in retry_nodes:
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id in ('compact', 'expanded'):
                child.id = 'same_function'
    assert ast.dump(ast.Module(body=retry_nodes[0].body, type_ignores=[])) == ast.dump(
        ast.Module(body=retry_nodes[1].body, type_ignores=[]))
    retry_guards = [node.body[0].body[0].lineno for node in retry_nodes]
    cov = coverage.Coverage(branch=True, source=[str(HERE)], data_file=str(RUNTIME / '.coverage-retry-fixture'))
    cov.start()
    fixture = load('_retry_layout_fixture', HERE / 'retry_fixture.py')
    for function in (fixture.compact, fixture.expanded):
        assert function(False) == 'accepted'
        try:
            function(True)
        except ValueError:
            pass
        else:
            raise AssertionError('Rejection not raised')
    cov.stop(); cov.save()
    cov.json_report(outfile=str(RUNTIME / 'retry-fixture-coverage.json'))
    payload = json.loads((RUNTIME / 'retry-fixture-coverage.json').read_text(encoding='utf-8'))
    row = next(row for name, row in payload['files'].items() if Path(name).name == 'retry_fixture.py')
    retry_layout = {name: [arc for arc in row['missing_branches'] if arc[0] == line]
                    for name, line in zip(('compact', 'expanded'), retry_guards)}

    with_tree = ast.parse((HERE / 'with_fixture.py').read_text(encoding='utf-8'))
    with_nodes = [node for node in with_tree.body if isinstance(node, ast.FunctionDef)
                  and node.name in ('compact', 'expanded')]
    assert ast.dump(ast.Module(body=with_nodes[0].body, type_ignores=[])) == ast.dump(
        ast.Module(body=with_nodes[1].body, type_ignores=[]))
    with_guards = [node.body[0].body[0].body[0].lineno for node in with_nodes]
    cov = coverage.Coverage(branch=True, source=[str(HERE)], data_file=str(RUNTIME / '.coverage-with-fixture'))
    cov.start()
    fixture = load('_with_layout_fixture', HERE / 'with_fixture.py')
    for function in (fixture.compact, fixture.expanded):
        assert function(False) == 'accepted'
        try:
            function(True)
        except ValueError:
            pass
        else:
            raise AssertionError('Context rejection not raised')
    cov.stop(); cov.save()
    cov.json_report(outfile=str(RUNTIME / 'with-fixture-coverage.json'))
    payload = json.loads((RUNTIME / 'with-fixture-coverage.json').read_text(encoding='utf-8'))
    row = next(row for name, row in payload['files'].items() if Path(name).name == 'with_fixture.py')
    with_layout = {name: [arc for arc in row['missing_branches'] if arc[0] == line]
                   for name, line in zip(('compact', 'expanded'), with_guards)}
    with_arcs = cov.get_data().arcs(str(HERE / 'with_fixture.py')) or []
    with_recorded = [list(arc) for arc in with_arcs if arc[0] == with_guards[0]]
    assert with_layout['compact'] and not with_layout['expanded']
    assert [with_guards[0], with_guards[0] - 1] in with_recorded

    tests = load('_existing_change_tests', ROOT / 'apps/backend/tests/unit/test_password_change_service.py')
    case_name = 'test_bad_source_or_truthy_verifier_never_reaches_global_lock'
    diagnostics = io.StringIO()
    cov = coverage.Coverage(branch=True, source=[str(PRODUCTION.parent)],
                            data_file=str(RUNTIME / '.coverage-existing'))
    cov.start()
    with redirect_stdout(diagnostics), redirect_stderr(diagnostics):
        measured = unittest.TextTestRunner(stream=diagnostics, verbosity=0).run(
            tests.PasswordChangeServiceTests(case_name))
    cov.stop(); cov.save()
    assert measured.wasSuccessful() and measured.testsRun == 1
    cov.json_report(outfile=str(RUNTIME / 'existing-coverage.json'))
    payload = json.loads((RUNTIME / 'existing-coverage.json').read_text(encoding='utf-8'))
    row = next(row for name, row in payload['files'].items() if Path(name).resolve() == PRODUCTION)
    missed = [arc for arc in row['missing_branches'] if arc[0] == guard_line]
    recorded = [list(arc) for arc in (cov.get_data().arcs(str(PRODUCTION)) or [])
                if arc[0] == guard_line]
    events = []

    def trace(frame, event, arg):
        if frame.f_code.co_filename == str(PRODUCTION) and frame.f_code.co_name == '_change':
            if event in ('line', 'exception'):
                # Do not collect arguments, exception messages, locals or secrets.
                events.append((event, frame.f_lineno))
        return trace

    previous = sys.gettrace()
    try:
        sys.settrace(trace)
        with redirect_stdout(diagnostics), redirect_stderr(diagnostics):
            traced = unittest.TextTestRunner(stream=diagnostics, verbosity=0).run(
                tests.PasswordChangeServiceTests(case_name))
    finally:
        sys.settrace(previous)
    assert traced.wasSuccessful() and traced.testsRun == 1
    exception_count = events.count(('exception', raise_line))
    assert exception_count == 2, ('guard rejection trace count', exception_count)
    if guard_line != raise_line:
        assert not missed, ('Expanded guard still missing', missed)
    print('BRANCH_AUDIT ' + json.dumps(dict(python=sys.version.split()[0], coverage=coverage.__version__,
        ast_equal=True, both_inputs_equal=True, layout_missing=layout, retry_layout_missing=retry_layout,
        context_layout_missing=with_layout,
        context_compact_recorded=with_recorded,
        existing_test=case_name, existing_pass=True, guard_line=guard_line, raise_line=raise_line,
        guard_exception_count=exception_count, guard_missing=missed,
        guard_recorded=recorded), sort_keys=True))
    print('PASS audit executed; audit itself does not edit production/exclusions/thresholds; single guard evidence is not full safety or Gate proof')


if __name__ == '__main__':
    main()
