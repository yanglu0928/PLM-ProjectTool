"""AST-identical layout check plus complete tests and actual create source chain."""
import ast
import io
import json
import runpy
import subprocess
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import coverage

ROOT = Path(__file__).resolve().parents[2]
RELATIVE = 'apps/backend/src/plm_assistant/modules/auth/application/managed_user_create.py'
PRODUCTION = ROOT / RELATIVE
RUNTIME = ROOT / '.poc-runtime/auth-security-create-layout'
BASELINE = 'eeb6558703b059f4742d9d95b8cc32efd60668ae'


def main():
    original = subprocess.run(['git', 'show', BASELINE + ':' + RELATIVE], cwd=ROOT,
                              check=True, capture_output=True, text=True, encoding='utf-8').stdout
    old = ast.parse(original)
    new = ast.parse(PRODUCTION.read_text(encoding='utf-8'))
    assert ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False)
    old_guards = {node.lineno: node for node in ast.walk(old) if isinstance(node, ast.If)}
    new_guards = [node for node in ast.walk(new) if isinstance(node, ast.If)]
    coordinates = []
    for line in (63, 65, 74, 75, 84, 88):
        matched = [node for node in new_guards if ast.dump(node) == ast.dump(old_guards[line])]
        assert len(matched) == 1 and isinstance(matched[0].body[0], ast.Raise)
        node = matched[0]
        assert node.body[0].lineno > node.end_lineno - 1 or node.body[0].lineno > node.lineno
        coordinates.append((line, node.lineno, node.body[0].lineno))
    RUNTIME.mkdir(parents=True, exist_ok=True)
    cov = coverage.Coverage(branch=True, source=[str(PRODUCTION.parent)], data_file=str(RUNTIME / '.coverage'))
    cov.start()
    diagnostics = io.StringIO()
    with redirect_stdout(diagnostics), redirect_stderr(diagnostics):
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'apps/backend/tests'), pattern='test_*.py')
        result = unittest.TextTestRunner(stream=diagnostics, verbosity=0).run(suite)
        runpy.run_path(str(ROOT / 'validation/aut-04-a12-p07-a13-p02-create-result-source/verify.py'), run_name='__main__')
    cov.stop()
    cov.save()
    cov.json_report(outfile=str(RUNTIME / 'coverage.json'))
    assert result.wasSuccessful()
    payload = json.loads((RUNTIME / 'coverage.json').read_text(encoding='utf-8'))
    row = next(row for path, row in payload['files'].items() if Path(path).resolve() == PRODUCTION)
    missing = row['missing_branches']
    for old_line, guard, raised in coordinates:
        assert not any(arc[0] == guard for arc in missing), (old_line, guard, missing)
        assert raised not in row['missing_lines'], raised
    print('CREATE_LAYOUT_RESULT ' + json.dumps(dict(ast_equal=True, baseline=BASELINE,
        test_count=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        actual_create_source_chain=True, coordinates=coordinates, file_summary=row['summary'],
        missing_branches=missing), sort_keys=True))
    print('PASS: layout-only coordinate correction; no new behavior tests or complete Auth/Gate claim.')


if __name__ == '__main__':
    main()
