"""Complete Auth scope with nineteen actual chains, preserved historical reports."""
import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / '.poc-runtime/auth-security-bootstrap-coverage'


def main():
    spec = spec_from_file_location('_bootstrap_full_coverage',ROOT / 'validation' /
                                  'aut-04-a12-p07-a01-security-coverage/verify.py')
    source = module_from_spec(spec)
    spec.loader.exec_module(source)
    source.main(runtime=RUNTIME,integrations=(
        'aut-04-a12-p06-a04-p02-a03-reset-history',
        'aut-04-a12-p06-a04-p02-a04-change-history',
        'aut-04-a12-p05-a07-windows-reset',
        'aut-04-a12-p04-a04-windows-password-change',
        'aut-04-a12-p07-a06-current-final',
        'aut-04-a03-windows-user-detail',
        'aut-04-a07-windows-user-list',
        'aut-04-a09-p05-windows-user-create',
        'aut-04-a10-p03-windows-user-name-patch',
        'aut-04-a11-p05-windows-user-state',
        'aut-03-a07-p03-production-login',
        'aut-04-a12-p07-a10-p02-session-source',
        'aut-04-a12-p07-a13-p02-create-result-source',
        'aut-04-a12-p07-a15-p02-state-final-source',
        'aut-04-a12-p07-a20-p02-name-database-source',
        'aut-04-a12-p07-a29-review-access-source',
        'aut-04-a12-p07-a31-project-read-source',
        'aut-04-a12-p07-a37-member-names-source',
        'aut-03-a06-initial-admin',
    ))
    payload = json.loads((RUNTIME / 'coverage.json').read_text(encoding='utf-8'))
    rows = [row['summary'] for name,row in payload['files'].items()
            if Path(name).resolve().is_relative_to(ROOT / 'apps/backend/src/plm_assistant/modules/auth')]
    totals = {key:sum(row[key] for row in rows) for key in
              ('covered_lines','num_statements','covered_branches','num_branches')}
    assert rows and totals['num_statements'] > 0 and totals['num_branches'] > 0
    passed = (10*totals['covered_lines'] >= 9*totals['num_statements'] and
              10*totals['covered_branches'] >= 9*totals['num_branches'])
    print('ALL_AUTH_THRESHOLD ' + json.dumps(totals | {'threshold_90_pass':passed},sort_keys=True))
    if not passed:
        raise SystemExit('ALL_AUTH INCOMPLETE: full Auth line and branch >=90% required; no Gate closure')


if __name__ == '__main__':
    main()
