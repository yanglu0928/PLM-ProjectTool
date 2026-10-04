"""Run real Session/Project/keyset fixture through authorized same-UOW resolution."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path

spec=spec_from_file_location("_audit_resolved_fixture",Path(__file__).resolve().parents[1]/"aud-02-a02-list-cursor"/"verify.py")
fixture=module_from_spec(spec)
spec.loader.exec_module(fixture)

if __name__=="__main__":
    fixture.main(resolved=True)
