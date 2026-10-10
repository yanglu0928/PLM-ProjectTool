"""Import the bundled application and check active declared dependencies in isolation."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from package_windows_unified_candidate import digest_path
from verify_windows_unified_extract import verify


KIND = "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE"
CURRENT_SHA256 = "eb2494be5de85b64a7ac64ce02112ed52454d0423d2a7e8406f120a126e14ed7"
STAGE_NAME = re.compile(r"plm-current-app-stage-[A-Za-z0-9_-]{8,64}\Z")
PROBE = r"""
import importlib
import importlib.metadata as metadata
import json
import pkgutil
from packaging.requirements import Requirement
import plm_assistant

dependencies = []
problems = []
declared = metadata.requires('plm-project-tool-backend') or []
for raw in declared:
    requirement = Requirement(raw)
    if requirement.marker and not requirement.marker.evaluate({'extra': ''}):
        continue
    try:
        version = metadata.version(requirement.name)
    except metadata.PackageNotFoundError:
        problems.append({'name': requirement.name, 'error': 'MISSING_DISTRIBUTION'})
        continue
    if requirement.specifier and not requirement.specifier.contains(version, prereleases=True):
        problems.append({'name': requirement.name, 'error': 'VERSION_MISMATCH'})
    dependencies.append(requirement.name)

modules = sorted(item.name for item in pkgutil.walk_packages(
    plm_assistant.__path__, plm_assistant.__name__ + '.'))
context_only = {'plm_assistant.migrations.env'}
failures = []
for name in modules:
    if name in context_only:
        continue  # Alembic provides context.config; actual migration is tested separately.
    try:
        importlib.import_module(name)
    except Exception as error:
        failures.append({'name': name, 'error_type': type(error).__name__})
print(json.dumps({'app_version': metadata.version('plm-project-tool-backend'),
                  'total_declared_dependency_count': len(declared),
                  'active_declared_dependency_count': len(dependencies),
                  'dependency_failures': problems, 'module_count': len(modules),
                  'context_only_excluded': sorted(context_only & set(modules)),
                  'import_failures': failures}, sort_keys=True))
"""


def audit(candidate: Path, stage: Path, temp_parent: Path,
          expected_sha256: str = CURRENT_SHA256) -> dict[str, object]:
    parent = temp_parent.resolve(strict=True)
    root = stage.resolve(strict=True)
    if (root.parent != parent or not str(root).isascii() or
            not STAGE_NAME.fullmatch(root.name) or stage.is_symlink() or
            digest_path(candidate) != expected_sha256):
        raise ValueError("current candidate or clean stage identity rejected")
    checked = verify(root, expected_kind=KIND)
    with zipfile.ZipFile(candidate) as archive:
        if (root / "manifest.json").read_bytes() != archive.read("manifest.json"):
            raise ValueError("current stage manifest differs from candidate")
    python = root / "payload/runtime/python.exe"
    if not python.is_file():
        raise ValueError("bundled Python missing")
    env = {name: value for name, value in os.environ.items()
           if not name.upper().startswith("PLM_") and name.upper() not in {"PYTHONPATH", "PYTHONHOME"}}
    result = subprocess.run([str(python), "-I", "-B", "-c", PROBE],
                            capture_output=True, text=True, errors="replace", env=env,
                            timeout=180, check=False)
    if result.returncode:
        raise ValueError("bundled Python import audit did not complete")
    try:
        report = json.loads(result.stdout.strip())
    except json.JSONDecodeError as error:
        raise ValueError("bundled Python import audit output invalid") from error
    if (report.get("app_version") != "0.1.0.dev0" or
            not isinstance(report.get("active_declared_dependency_count"), int) or
            not isinstance(report.get("module_count"), int) or
            report.get("total_declared_dependency_count") != 18 or
            report["active_declared_dependency_count"] != 17 or
            report["module_count"] != 586 or
            report.get("context_only_excluded") != ["plm_assistant.migrations.env"] or
            report.get("dependency_failures") or report.get("import_failures")):
        raise ValueError("bundled dependency or module import failure: " +
                         json.dumps({"dependencies": report.get("dependency_failures"),
                                     "imports": report.get("import_failures")}, sort_keys=True))
    if digest_path(candidate) != expected_sha256:
        raise ValueError("candidate changed during runtime audit")
    return {"status": "CURRENT_APP_BUNDLED_RUNTIME_IMPORT_PASS",
            "candidate_sha256": expected_sha256,
            "payload_file_count": checked["payload_file_count"], **report,
            "release_eligible": False, "existing_database_connected": False,
            "services_started": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--stage", required=True, type=Path)
    parser.add_argument("--temp-parent", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.candidate, args.stage, args.temp_parent),
                     ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
