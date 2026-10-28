"""Safely stage a verified Windows parent candidate under hosted runner temp only."""
from __future__ import annotations

import base64
import hashlib
import json
import ssl
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath


META = {"manifest.json", "payload-sha256sums.txt"}
BLOCKED_SUFFIXES = {".key", ".pfx", ".p12", ".pem", ".env", ".log"}
PUBLIC_CA_BUNDLE = "payload/runtime/packages/certifi/cacert.pem"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_public_ca_bundle(data: bytes) -> bool:
    if b"PRIVATE KEY" in data:
        return False
    try:
        text = data.decode("ascii", errors="strict")
    except UnicodeDecodeError:
        return False

    lines = text.splitlines()
    begin = "-----BEGIN CERTIFICATE-----"
    end = "-----END CERTIFICATE-----"
    in_certificate = False
    encoded = []
    certificates = []
    for line in lines:
        if not in_certificate:
            if not line.strip():
                continue
            if line.startswith("#"):
                if any(ord(char) < 32 or ord(char) > 126 for char in line):
                    return False
                continue
            if line != begin:
                return False
            in_certificate = True
            encoded = []
            continue

        if line == end:
            if not encoded:
                return False
            try:
                der = base64.b64decode("".join(encoded), validate=True)
            except (ValueError, base64.binascii.Error):
                return False
            if not der or der[0] != 0x30:
                return False
            certificates.append(begin + "\n" + "\n".join(encoded) + "\n" + end)
            in_certificate = False
            encoded = []
            continue
        if not line or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for char in line):
            return False
        encoded.append(line)

    if in_certificate or not certificates:
        return False
    try:
        # OpenSSL parses public certificate blocks without network access.
        ssl.create_default_context().load_verify_locations(cadata="\n".join(certificates))
    except (OSError, ssl.SSLError, ValueError):
        return False
    return True


def safe_name(name: str) -> str:
    path = PurePosixPath(name)
    if (not name or name.startswith(("/", "\\")) or "\\" in name or ":" in name
            or any(part in ("", ".", "..") for part in path.parts)
            or any(part.rstrip(" .") != part or part.endswith(".") for part in path.parts)
            or any(part.split(".")[0].casefold() in
                   {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                    *(f"lpt{i}" for i in range(1, 10))} for part in path.parts)):
        raise ValueError("unsafe candidate path")
    suffix = Path(name).suffix.casefold()
    if suffix in BLOCKED_SUFFIXES and not (suffix == ".pem" and name == PUBLIC_CA_BUNDLE):
        raise ValueError("candidate contains prohibited suffix: " + suffix)
    return name


def ensure_runner_temp(path: Path) -> Path:
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    target_parent = path.parent.resolve(strict=True)
    if (target_parent != runner_temp or path.drive.casefold() == "c:"
            or path.exists() or path.is_symlink()):
        raise ValueError("staging target must be a new direct child of non-C RUNNER_TEMP")
    return runner_temp


def stage_candidate(archive: Path, summary_path: Path, target: Path) -> dict:
    runner_temp = ensure_runner_temp(target)
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("candidate archive missing or linked")
    if summary_path.is_symlink() or not summary_path.is_file():
        raise ValueError("candidate summary missing or linked")
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    archive_hash = sha_file(archive)
    if (summary.get("status") != "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE_INTEGRITY_PASS"
            or summary.get("release_eligible") is not False
            or summary.get("legal_clearance") is not False
            or summary.get("archive_sha256") != archive_hash):
        raise ValueError("candidate summary or archive identity rejected")

    staging = Path(tempfile.mkdtemp(prefix=".plm-candidate-stage-", dir=runner_temp))
    staging_resolved = staging.resolve(strict=True)
    if staging_resolved.parent != runner_temp:
        raise ValueError("staging temporary path escaped RUNNER_TEMP")
    committed = False
    try:
        with zipfile.ZipFile(archive) as source:
            infos = source.infolist()
            names = [safe_name(info.filename) for info in infos]
            if len(names) != len(set(name.casefold() for name in names)):
                raise ValueError("candidate has duplicate or case-conflicting paths")
            if any((info.external_attr >> 16) & 0o170000 == 0o120000 for info in infos):
                raise ValueError("candidate symlink rejected")
            manifest = json.loads(source.read("manifest.json"))
            if (manifest.get("kind") != "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE"
                    or manifest.get("release_eligible") is not False
                    or manifest.get("legal_clearance") is not False
                    or manifest.get("source_commit") != summary.get("source_commit")
                    or str(manifest.get("workflow_run")) != str(summary.get("workflow_run"))):
                raise ValueError("candidate manifest state or provenance rejected")
            sums = source.read("payload-sha256sums.txt")
            if sha_bytes(sums) != manifest.get("payload_sha256sums_sha256"):
                raise ValueError("candidate checksum list identity mismatch")
            expected = {}
            for line in sums.decode("ascii").splitlines():
                digest, name = line.split("  ", 1)
                safe_name(name)
                if not re.fullmatch(r"[0-9a-f]{64}", digest) or name in expected:
                    raise ValueError("malformed candidate checksum entry")
                expected[name] = digest
            if (len(expected) != manifest.get("payload_file_count")
                    or set(names) != set(expected) | META):
                raise ValueError("candidate inventory differs from its manifest")
            for name, digest in expected.items():
                info = source.getinfo(name)
                if Path(name).suffix.casefold() == ".pem":
                    if name != PUBLIC_CA_BUNDLE:
                        raise ValueError("candidate contains non-allowlisted PEM file")
                    ca_bytes = source.read(info)
                    if not validate_public_ca_bundle(ca_bytes):
                        raise ValueError("allowlisted certifi bundle is not public-certificate-only")
                    if not validate_public_ca_bundle(b"# hosted public CA bundle comment\n" + ca_bytes):
                        raise ValueError("ASCII comment line in public CA bundle was rejected")
                    invalid_bundles = (
                        b"# comment\n-----BEGIN PRIVATE KEY-----\nAA==\n-----END PRIVATE KEY-----\n",
                        b"# comment\nunknown text\n" + ca_bytes,
                        b"-----BEGIN CERTIFICATE-----\nnot-base64!\n-----END CERTIFICATE-----\n",
                        b"-----BEGIN CERTIFICATE-----\nAA==\n",
                    )
                    for case_number, candidate in enumerate(invalid_bundles, start=1):
                        if validate_public_ca_bundle(candidate):
                            raise ValueError(f"invalid public CA bundle case {case_number} was accepted")
                destination = staging.joinpath(*PurePosixPath(name).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                actual = hashlib.sha256()
                with source.open(info) as input_stream, destination.open("xb") as output_stream:
                    for block in iter(lambda: input_stream.read(1024 * 1024), b""):
                        output_stream.write(block)
                        actual.update(block)
                if actual.hexdigest() != digest:
                    raise ValueError("candidate payload hash mismatch")
            (staging / "manifest.json").write_bytes(source.read("manifest.json"))
            (staging / "payload-sha256sums.txt").write_bytes(sums)

        if target.exists() or target.is_symlink():
            raise ValueError("staging target appeared during extraction")
        os.replace(staging, target)
        committed = True
        receipt = {
            "status": "HOSTED_WINDOWS_CANDIDATE_STAGING_PASS_LIMITED",
            "archive_sha256": archive_hash,
            "payload_file_count": len(expected),
            "release_eligible": False,
            "legal_clearance": False,
            "installation_performed": False,
            "services_started": False,
        }
        (target / "candidate-staging-receipt.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return receipt
    except Exception:
        cleanup = target if committed else staging
        if cleanup.exists():
            resolved = cleanup.resolve(strict=True)
            if resolved.parent != runner_temp or resolved.drive.casefold() == "c:":
                raise RuntimeError("refusing to clean outside runner-owned temp")
            shutil.rmtree(cleanup)
        raise
