"""AST-equivalent service layout and unchanged actual acceptance scope."""
import ast
import subprocess
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = 'c004980'


def main():
    for filename in ('password_change.py', 'password_reset.py'):
        relative = 'apps/backend/src/plm_assistant/modules/auth/application/' + filename
        original = subprocess.run(['git', 'show', BASELINE + ':' + relative], cwd=ROOT,
                                  check=True, capture_output=True).stdout.decode('utf-8')
        current = (ROOT / relative).read_text(encoding='utf-8')
        assert ast.dump(ast.parse(original)) == ast.dump(ast.parse(current)), ('Non-equivalent AST', filename)
        print('PASS AST equivalent ' + filename + ' to ' + BASELINE, flush=True)
    spec = spec_from_file_location('_service_layout_coverage', ROOT / 'validation' /
                                  'aut-04-a12-p07-a01-security-coverage' / 'verify.py')
    source = module_from_spec(spec)
    spec.loader.exec_module(source)
    source.main(runtime=ROOT / '.poc-runtime/auth-security-service-layout-coverage', integrations=(
        'aut-04-a12-p06-a04-p02-a03-reset-history',
        'aut-04-a12-p06-a04-p02-a04-change-history',
        'aut-04-a12-p05-a07-windows-reset',
        'aut-04-a12-p04-a04-windows-password-change',
        'aut-04-a12-p07-a06-current-final',
    ))


if __name__ == '__main__':
    main()
