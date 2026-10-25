"""Full actual coverage including final-proof database faults."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = spec_from_file_location('_final_fault_coverage', ROOT / 'validation' /
                              'aut-04-a12-p07-a01-security-coverage' / 'verify.py')
source = module_from_spec(spec)
spec.loader.exec_module(source)

if __name__ == '__main__':
    source.main(runtime=ROOT / '.poc-runtime/auth-security-final-fault-coverage', integrations=(
        'aut-04-a12-p06-a04-p02-a03-reset-history',
        'aut-04-a12-p06-a04-p02-a04-change-history',
        'aut-04-a12-p05-a07-windows-reset',
        'aut-04-a12-p04-a04-windows-password-change',
        'aut-04-a12-p07-a06-current-final',
    ))
