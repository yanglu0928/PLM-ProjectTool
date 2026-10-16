"""AST-identical state guard layout with full tests and actual final-source chain."""
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
RELATIVE = 'apps/backend/src/plm_assistant/modules/auth/application/user_state.py'
PRODUCTION = ROOT / RELATIVE
RUNTIME = ROOT / '.poc-runtime/auth-security-state-layout'
BASELINE = 'be1d88f745881e1089d3b01755b62e9981389215'


def main():
    original = subprocess.run(['git', 'show', BASELINE + ':' + RELATIVE], cwd=ROOT,
                              check=True, capture_output=True, text=True, encoding='utf-8').stdout
    old = ast.parse(original)
    new = ast.parse(PRODUCTION.read_text(encoding='utf-8'))
    assert ast.dump(old) == ast.dump(new)
    old_guards = {node.lineno: node for node in ast.walk(old) if isinstance(node, ast.If)}
    new_guards = [node for node in ast.walk(new) if isinstance(node, ast.If)]
    coordinates = []
    for line in (101,111,116,127):
        matched = [node for node in new_guards if ast.dump(node) == ast.dump(old_guards[line])]
        assert len(matched) == 1
        node = matched[0]
        assert isinstance(node.body[0], ast.Raise) and node.body[0].lineno > node.test.end_lineno
        coordinates.append((line,node.lineno,node.body[0].lineno))
    RUNTIME.mkdir(parents=True, exist_ok=True)
    cov = coverage.Coverage(branch=True, source=[str(PRODUCTION.parent)], data_file=str(RUNTIME / '.coverage'))
    cov.start()
    diagnostics = io.StringIO()
    with redirect_stdout(diagnostics), redirect_stderr(diagnostics):
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'apps/backend/tests'), pattern='test_*.py')
        result = unittest.TextTestRunner(stream=diagnostics, verbosity=0).run(suite)
        runpy.run_path(str(ROOT / 'validation/aut-04-a12-p07-a15-p02-state-final-source/verify.py'), run_name='__main__')
    cov.stop()
    cov.save()
    assert result.wasSuccessful()
    cov.json_report(outfile=str(RUNTIME / 'coverage.json'))
    payload = json.loads((RUNTIME / 'coverage.json').read_text(encoding='utf-8'))
    row = next(row for path,row in payload['files'].items() if Path(path).resolve() == PRODUCTION)
    for old_line,guard,raised in coordinates:
        assert not any(arc[0] == guard for arc in row['missing_branches']), (old_line,guard)
        assert raised not in row['missing_lines']
    print('STATE_LAYOUT_RESULT ' + json.dumps(dict(ast_equal=True,baseline=BASELINE,
        test_count=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        actual_state_final_chain=True,coordinates=coordinates,file_summary=row['summary'],
        missing_branches=row['missing_branches']),sort_keys=True))
    print('PASS: layout-only coordinate correction; actual rollback chain retained, no complete Auth/Gate claim.')


if __name__ == '__main__':
    main()
