"""Actual current Admin and narrow first self reset final proof, with source regression."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
spec=spec_from_file_location('_reset_current_admin_source',Path(__file__).resolve().parents[1]/'aut-04-a12-p05-a03-reset-password-source'/'verify.py')
source=module_from_spec(spec);spec.loader.exec_module(source)
if __name__=='__main__':source.m.fixture.main(exercise=lambda v:source.exercise(v,access_checks=True))
