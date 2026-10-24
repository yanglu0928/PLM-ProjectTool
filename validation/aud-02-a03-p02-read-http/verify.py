"""Actual opt-in HTTP plus real Session/Project/PostgreSQL Audit; License synthetic."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path

spec=spec_from_file_location("_audit_http_fixture",Path(__file__).resolve().parents[1]/"aud-02-a02-list-cursor"/"verify.py")
fixture=module_from_spec(spec)
spec.loader.exec_module(fixture)

if __name__=="__main__":
    fixture.main(resolved=True,http=True)
