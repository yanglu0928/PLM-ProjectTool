"""Assemble same-run Windows runtime component artifacts into a non-release parent candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import uuid
import zipfile
from pathlib import Path, PurePosixPath


BLOCKED = {".env", ".log", ".key", ".pfx", ".p12", ".pyc"}
COMPONENT_META = {"manifest.json", "third-party-inventory.json", "payload-sha256sums.txt"}
DATABASE_CREDENTIAL_TARGET = "PLMProjectTool/Database"


def make_startup_preflight(*, product_key_present: bool) -> dict[str, object]:
    blockers = [] if product_key_present else ["FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED"]
    blockers.extend([
        "FORMAL_LICENSE_TRUST_NOT_VERIFIED",
        "DATABASE_CREDENTIAL_REFERENCE_NOT_VERIFIED",
        "SERVICE_IDENTITY_ACL_NOT_VERIFIED",
        "TLS_CERTIFICATE_CONFIGURATION_NOT_VERIFIED",
    ])
    return {
        "formal_startup_ready": False,
        "packaged_product_public_key_resource_present": product_key_present,
        "formal_license_trust_verified": False,
        "database_credential_target_reference": DATABASE_CREDENTIAL_TARGET,
        "database_credential_reference_verified": False,
        "service_identity_acl_verified": False,
        "tls_certificate_configured": False,
        "tls_private_key_configured": False,
        "blocker_codes": blockers,
    }


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_name(name: str) -> str:
    parts = PurePosixPath(name).parts
    if (not name or name.startswith(("/", "\\")) or "\\" in name or ":" in name
            or any(p in ("", ".", "..") for p in parts)):
        raise ValueError(f"unsafe archive path: {name!r}")
    return name


def one_file(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern))
    if len(matches) != 1 or not matches[0].is_file() or matches[0].is_symlink():
        raise ValueError(f"expected exactly one regular file matching {pattern}")
    return matches[0]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def checked_zip(path: Path, kind: str, source_commit: str | None = None) -> tuple[dict, dict, dict]:
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        names = [safe_name(i.filename) for i in infos]
        if len(names) != len(set(n.casefold() for n in names)):
            raise ValueError(f"{kind}: duplicate/case-conflicting ZIP paths")
        if any((i.external_attr >> 16) & 0o170000 == 0o120000 for i in infos):
            raise ValueError(f"{kind}: symlink entry rejected")
        manifest = json.loads(z.read("manifest.json"))
        if manifest.get("release_eligible") is not False or manifest.get("legal_clearance") is not False:
            raise ValueError(f"{kind}: release/legal state is not explicitly blocked")
        if source_commit and manifest.get("source_commit") != source_commit:
            raise ValueError(f"{kind}: source commit mismatch")
        checksums = {}
        for line in z.read("payload-sha256sums.txt").decode("ascii").splitlines():
            digest, name = line.split("  ", 1)
            safe_name(name)
            if name in checksums or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"{kind}: malformed/duplicate checksum line")
            checksums[name] = digest
        if not checksums or set(checksums) - set(names):
            raise ValueError(f"{kind}: checksum references missing payload")
        for name, expected in checksums.items():
            if sha_bytes(z.read(name)) != expected:
                raise ValueError(f"{kind}: payload hash mismatch: {name}")
        payload_names = set(checksums)
        if any(n not in payload_names and n not in COMPONENT_META for n in names):
            raise ValueError(f"{kind}: unlisted archive entry")
        if set(names) != payload_names | COMPONENT_META:
            raise ValueError(f"{kind}: component inventory mismatch")
        inventory = json.loads(z.read("third-party-inventory.json"))
        return manifest, checksums, inventory


def add_zip_payload(bundle: zipfile.ZipFile, src_zip: Path, checksums: dict[str, str],
                    prefix: str, parent_hashes: dict[str, str]) -> None:
    with zipfile.ZipFile(src_zip) as src:
        for name in sorted(checksums):
            if not name.startswith(prefix):
                raise ValueError(f"component payload outside expected prefix: {name}")
            target = safe_name(name)
            if target in parent_hashes:
                raise ValueError(f"parent package collision: {target}")
            data = src.read(name)
            digest = sha_bytes(data)
            parent_hashes[target] = digest
            bundle.writestr(target, data)


def build(args: argparse.Namespace) -> dict:
    commit = args.source_commit
    run_id = args.run_id
    for root in (args.backend_dir, args.frontend_dir, args.pg_dir, args.embedded_dir, args.caddy_dir):
        if not root.is_dir() or root.is_symlink():
            raise ValueError("all component artifact roots must be existing real directories")

    backend_manifest_file = one_file(args.backend_dir, "cloud-build-manifest.json")
    backend_manifest = read_json(backend_manifest_file)
    wheel = one_file(args.backend_dir, "*.whl")
    if (backend_manifest.get("source_commit") != commit
            or str(backend_manifest.get("workflow_run")) != run_id
            or backend_manifest.get("sha256") != sha_file(wheel)
            or backend_manifest.get("file") != wheel.name
            or backend_manifest.get("release_eligible") is not False):
        raise ValueError("backend artifact provenance/hash mismatch")

    frontend_manifest_file = one_file(args.frontend_dir, "cloud-build-manifest.json")
    frontend_manifest = read_json(frontend_manifest_file)
    if (frontend_manifest.get("source_commit") != commit
            or str(frontend_manifest.get("workflow_run")) != run_id
            or frontend_manifest.get("release_eligible") is not False):
        raise ValueError("frontend artifact provenance mismatch")
    frontend_hashes = frontend_manifest.get("files")
    frontend_files = {}
    for path in sorted(args.frontend_dir.rglob("*")):
        if path.is_dir():
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError("frontend artifact link/non-file rejected")
        rel = path.relative_to(args.frontend_dir).as_posix()
        if rel == "cloud-build-manifest.json":
            continue
        if rel not in frontend_hashes or sha_file(path) != frontend_hashes[rel]:
            raise ValueError(f"frontend file provenance mismatch: {rel}")
        frontend_files[rel] = path
    if set(frontend_files) != set(frontend_hashes) or not frontend_files:
        raise ValueError("frontend artifact inventory incomplete")

    embedded_zip = one_file(args.embedded_dir, "*.zip")
    embedded_summary = args.embedded_dir / "embedded-backend-summary.json"
    if not embedded_summary.is_file() or embedded_summary.is_symlink():
        raise ValueError("embedded backend summary missing")
    embedded_result = read_json(embedded_summary)
    if (embedded_result.get("release_eligible") is not False
            or embedded_result.get("status") != "NON_RELEASE_EMBEDDED_BACKEND_INTEGRITY_PASS"
            or embedded_result.get("source_commit") != commit
            or embedded_result.get("archive_sha256") != sha_file(embedded_zip)):
        raise ValueError("embedded candidate verification summary mismatch")
    embedded_manifest, embedded_hashes, embedded_inventory = checked_zip(
        embedded_zip, "embedded", commit)
    if (embedded_manifest.get("source_commit") != commit
            or embedded_manifest.get("kind") != "WINDOWS_EMBEDDED_BACKEND_NON_RELEASE_CANDIDATE"):
        raise ValueError("embedded manifest identity mismatch")

    pg_zip = one_file(args.pg_dir, "*.zip")
    pg_summary = args.pg_dir / "pg18-rebuilt-summary.json"
    if not pg_summary.is_file() or pg_summary.is_symlink():
        raise ValueError("PG18 rebuild summary missing")
    pg_result = read_json(pg_summary)
    if (pg_result.get("status") != "NON_RELEASE_PG18_RUNTIME_REBUILT_INTEGRITY_PASS"
            or pg_result.get("release_eligible") is not False
            or pg_result.get("legal_clearance") is not False
            or pg_result.get("archive_sha256") != sha_file(pg_zip)):
        raise ValueError("PG18 artifact verification summary mismatch")
    pg_manifest, pg_hashes, pg_inventory = checked_zip(pg_zip, "pg18")
    if (pg_manifest.get("kind") != "WINDOWS_PG18_PGVECTOR_RUNTIME_NON_RELEASE_REBUILT"
            or pg_manifest.get("postgresql_version") != "18.6"
            or pg_manifest.get("pgvector_version") != "0.8.6"):
        raise ValueError("PG18 manifest identity mismatch")
    if any(not name.startswith(("payload/pgsql/", "payload/third-party-licenses/"))
           for name in pg_hashes):
        raise ValueError("PG18 payload contains unexpected path")

    caddy_zip = one_file(args.caddy_dir, "caddy_2.11.4_windows_amd64.zip")
    caddy_audit = read_json(one_file(args.caddy_dir, "caddy-audit.json"))
    if (caddy_audit.get("status") != "PINNED_OFFICIAL_INPUT_PASS_NOT_RELEASE_READY"
            or caddy_audit.get("release_eligible") is not False
            or caddy_audit.get("version") != "2.11.4"
            or caddy_audit.get("platform") != "Windows AMD64"):
        raise ValueError("Caddy input audit is missing or release state changed")
    if caddy_zip.stat().st_size != 17559418 or sha_file(caddy_zip) != "1708333f79e274c7697285afe6d592ab39314e0b131e9ec6bea08ad27df62ebf":
        raise ValueError("Caddy official ZIP size/hash mismatch")
    with zipfile.ZipFile(caddy_zip) as z:
        if set(z.namelist()) != {"caddy.exe", "LICENSE", "README.md"}:
            raise ValueError("Caddy ZIP inventory mismatch")
        caddy_payload = {
            "payload/runtime/caddy/caddy.exe": z.read("caddy.exe"),
            "payload/third-party-licenses/caddy/LICENSE": z.read("LICENSE"),
            "payload/third-party-licenses/caddy/README.md": z.read("README.md"),
        }
    if sha_bytes(caddy_payload["payload/runtime/caddy/caddy.exe"]) != "5cb9ab71e5756ce72840b8234177a2f40c8b4ab47a806b8e841e2b784e9df62b":
        raise ValueError("Caddy executable hash mismatch")

    source_config = Path(__file__).resolve().parent.parent / "apps" / "backend" / "config" / "bootstrap.example.yaml"
    if not source_config.is_file() or source_config.is_symlink():
        raise ValueError("non-secret bootstrap source example missing")
    config_text = source_config.read_text(encoding="utf-8")
    old_root = 'data_root: "C:/PLMTool/data"'
    if config_text.count(old_root) != 1:
        raise ValueError("bootstrap source example default changed unexpectedly")
    config_text = config_text.replace(old_root, 'data_root: "D:/PLMTool/data"', 1)
    noncomment_keys = [
        line.split(":", 1)[0].strip()
        for line in config_text.splitlines()
        if line.strip() and not line.lstrip().startswith("#") and ":" in line
    ]
    if any(key.casefold() in {"password", "api_key", "token", "private_key",
                              "license_key", "database_url", "secret"}
           for key in noncomment_keys):
        raise ValueError("bootstrap sample contains a secret-bearing key")
    first_readme = """# PLM Project Tool — Windows package candidate

This is a non-release candidate. It has not been installed, the application API has not been started, and legal, product trust, service account, HTTPS, OCR model, and user acceptance checks remain open.

## Bootstrap example

Copy `config/bootstrap.example.yaml` to a protected deployment configuration location and review every setting before use. The sample uses `D:/PLMTool/data` to avoid placing application data on C:. Confirm that D: exists and has sufficient space and restricted write access; if it does not, change `data_root` to another absolute path on a suitable volume.

The YAML file contains non-secret settings only. Do not put database passwords, API keys, License material, or private keys in it. Database credentials must come from the approved Windows credential store. Do not start the product service until the real packaged product public key, License trust, service account, and ACL have been provisioned and independently checked.

## Package layout

- `runtime/`: embedded Python and backend runtime
- `frontend/dist/`: built web interface
- `pgsql/`: PostgreSQL 18.6 and pgvector 0.8.6 binaries
- `config/`: non-secret example only
- `provenance/`: component build manifests and inventories

This archive is not an installer or a Pilot release. Its PostgreSQL component was exercised only with a temporary local database on a hosted runner.

## Read-only startup preflight

Run `powershell -NoProfile -File .\\payload\\check-startup.ps1` from the extracted package folder. The command reads only the package manifest and prints a short, non-secret list of missing startup prerequisites. This non-release candidate will report `BLOCKED` and exit with code 2. It does not read credentials, start a service, or make the package release-ready. If you run `powershell -NoProfile -File .\\payload\\start-trial.ps1`, the launcher repeats that verified BLOCKED report and still exits with code 1 before starting any service.
"""
    launcher_path = Path(__file__).with_name("start_windows_trial_candidate.ps1")
    if not launcher_path.is_file() or launcher_path.is_symlink():
        raise ValueError("fail-closed startup guard source missing")
    launcher_bytes = launcher_path.read_bytes()
    if any(token in launcher_bytes.lower() for token in
           (b"-----begin private key-----", b"api_key:", b"password:", b".pfx", b".p12")):
        raise ValueError("startup guard source contains a secret marker or private-file reference")
    diagnostic_path = Path(__file__).with_name("check_windows_trial_preflight.ps1")
    if not diagnostic_path.is_file() or diagnostic_path.is_symlink():
        raise ValueError("read-only startup diagnostic source missing")
    diagnostic_bytes = diagnostic_path.read_bytes()
    if any(token in diagnostic_bytes.lower() for token in
           (b"-----begin private key-----", b"api_key:", b"password:", b".pfx", b".p12")):
        raise ValueError("startup diagnostic source contains a secret marker or private-file reference")
    package_docs = {
        "payload/config/bootstrap.example.yaml": config_text.encode("utf-8"),
        "payload/README-FIRST.md": first_readme.encode("utf-8"),
        "payload/start-trial.ps1": launcher_bytes,
        "payload/check-startup.ps1": diagnostic_bytes,
    }

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    archive = output / f"NOT-FOR-RELEASE-windows-parent-{run_id}.zip"
    hashes: dict[str, str] = {}
    product_key_path = "payload/runtime/packages/plm_assistant/modules/license/trust/product_public_key.json"
    product_key_present = product_key_path in embedded_hashes
    startup_preflight = make_startup_preflight(product_key_present=product_key_present)

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as bundle:
        add_zip_payload(bundle, embedded_zip, embedded_hashes, "payload/runtime/", hashes)
        add_zip_payload(bundle, pg_zip, pg_hashes, "payload/", hashes)
        for rel, path in sorted(frontend_files.items()):
            target = safe_name("payload/frontend/dist/" + rel)
            if target in hashes:
                raise ValueError("frontend target collision")
            hashes[target] = sha_file(path)
            bundle.write(path, target)

        for target, data in sorted(package_docs.items()):
            hashes[safe_name(target)] = sha_bytes(data)
            bundle.writestr(target, data)
        for target, data in sorted(caddy_payload.items()):
            hashes[safe_name(target)] = sha_bytes(data)
            bundle.writestr(target, data)

        evidence = {
            "backend-cloud-build-manifest.json": backend_manifest,
            "frontend-cloud-build-manifest.json": frontend_manifest,
            "embedded-backend-manifest.json": embedded_manifest,
            "embedded-backend-third-party-inventory.json": embedded_inventory,
            "pg18-manifest.json": pg_manifest,
            "pg18-third-party-inventory.json": pg_inventory,
            "caddy-input-audit.json": caddy_audit,
        }
        for name, value in evidence.items():
            target = "provenance/" + name
            data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
            hashes[target] = sha_bytes(data)
            bundle.writestr(target, data)

        sums = "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())).encode("ascii")
        manifest = {
            "kind": "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE",
            "schema_version": "plm.windows-parent-package.v1",
            "release_eligible": False,
            "legal_clearance": False,
            "source_commit": commit,
            "workflow_run": run_id,
            "components": {
                "backend_wheel_sha256": sha_file(wheel),
                "embedded_backend_archive_sha256": sha_file(embedded_zip),
                "frontend_file_count": len(frontend_files),
                "pg18_archive_sha256": sha_file(pg_zip),
                "caddy_executable_sha256": sha_bytes(caddy_payload["payload/runtime/caddy/caddy.exe"]),
                "caddy_version": "2.11.4",
                "postgresql_version": "18.6", "pgvector_version": "0.8.6",
            },
            "payload_file_count": len(hashes),
            "bootstrap_example_data_root": "D:/PLMTool/data",
            "bootstrap_is_example_only": True,
            "startup_preflight": startup_preflight,
            "payload_sha256sums_sha256": sha_bytes(sums),
            "known_gaps": [
                "not installed or started; no packaged Edge/HTTPS/PostgreSQL smoke",
                "OCR native system components and approved model files are not integrated",
                "formal service account, ACL, installer/upgrade and product public-key trust are incomplete",
                "third-party legal review, Gate 3 through Gate 7 and UAT remain open",
                "Windows Server 2025 product and Debian 13 acceptance remain open",
            ],
        }
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        bundle.writestr("payload-sha256sums.txt", sums)
        bundle.writestr("manifest.json", manifest_bytes)

    expected = {**hashes, "payload-sha256sums.txt": sha_bytes(sums),
                "manifest.json": sha_bytes(manifest_bytes)}
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(n.casefold() for n in names)) or set(names) != set(expected):
            raise ValueError("parent package ZIP inventory mismatch")
        for name, expected_digest in expected.items():
            h = hashlib.sha256()
            with bundle.open(name) as f:
                for block in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(block)
            if h.hexdigest() != expected_digest:
                raise ValueError("parent package readback mismatch: " + name)

    result = {
        "status": "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE_INTEGRITY_PASS",
        "release_eligible": False, "legal_clearance": False,
        "source_commit": commit, "workflow_run": run_id,
        "archive": archive.name, "archive_sha256": sha_file(archive),
        "archive_bytes": archive.stat().st_size, "payload_file_count": len(hashes),
        "backend_distribution_count": embedded_manifest.get("distribution_count"),
        "frontend_file_count": len(frontend_files), "pg18_payload_file_count": len(pg_hashes),
        "installation_performed": False, "database_started": False,
        "startup_preflight": startup_preflight,
    }
    (output / "verification-summary.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-dir", type=Path, required=True)
    parser.add_argument("--frontend-dir", type=Path, required=True)
    parser.add_argument("--pg-dir", type=Path, required=True)
    parser.add_argument("--embedded-dir", type=Path, required=True)
    parser.add_argument("--caddy-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args), ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
