"""Same full integration measurement after HTTP defensive unit additions."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = spec_from_file_location('_defensive_coverage_source', ROOT / 'validation' /
                              'aut-04-a12-p07-a01-security-coverage' / 'verify.py')
source = module_from_spec(spec)
spec.loader.exec_module(source)

if __name__ == '__main__':
    source.main(runtime=ROOT / '.poc-runtime/auth-security-http-defensive-coverage', integrations=(
        'aut-04-a12-p06-a04-p02-a03-reset-history',
        'aut-04-a12-p06-a04-p02-a04-change-history',
        'aut-04-a12-p05-a07-windows-reset',
        'aut-04-a12-p04-a04-windows-password-change',
    ))
