"""Read-only marker/OS cross-check; a diagnostic, never shutdown clearance."""

from __future__ import annotations

import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path, PureWindowsPath

from plm_assistant import __version__
from .runtime_process_identity import package_code_digest
from .windows_process_inventory import ProcessAssessment, ProcessObservation


_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_FILE_NAME = re.compile(r"(api|audit_worker|parser_worker)-([1-9][0-9]*)-([a-f0-9]{32})\.json\Z")
_SID = re.compile(r"S-\d-\d+(?:-\d+)+\Z", re.ASCII)
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_ROLE_ENTRY = {
    "API": re.compile(
        r"plm_assistant[./\\]entrypoints[./\\]"
        r"(?:serve_windows(?:\.py)?\b|service_windows(?:\.py)?\s+API\b)", re.I),
    "AUDIT_WORKER": re.compile(r"plm_assistant[./\\]entrypoints[./\\](?:worker_windows(?:\.py)?|service_windows(?:\.py)?\s+AUDIT_WORKER)\b", re.I),
    "PARSER_WORKER": re.compile(r"plm_assistant[./\\]entrypoints[./\\](?:parser_worker_windows(?:\.py)?|service_windows(?:\.py)?\s+PARSER_WORKER)\b", re.I),
}
_FIELDS = frozenset({"schema_version", "role", "pid", "registered_at_utc",
                     "package_version", "code_sha256", "owner_sid",
                     "executable_path", "nonce"})


class WindowsMarkerReconciliationError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("WINDOWS_MARKER_RECONCILIATION_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class MarkerFinding:
    pid: int
    role: str
    status: str


@dataclass(frozen=True, slots=True)
class MarkerAssessment:
    findings: tuple[MarkerFinding, ...]
    unmatched_candidates: tuple[int, ...]
    classification: str = "DIAGNOSTIC_ONLY"


def _checked_directory(path: Path) -> None:
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & _REPARSE):
        raise WindowsMarkerReconciliationError()


def _unique_fields(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise WindowsMarkerReconciliationError()
        result[key] = value
    return result


def _utc_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise WindowsMarkerReconciliationError()
    return parsed.astimezone(timezone.utc)


def _read_markers(data_root: Path) -> tuple[dict, ...]:
    if (sys.platform != "win32" or not isinstance(data_root, Path)
            or not data_root.is_absolute()
            or PureWindowsPath(str(data_root)).drive.startswith("\\\\")):
        raise WindowsMarkerReconciliationError()
    for ancestor in (data_root, *data_root.parents):
        _checked_directory(ancestor)
    directory = data_root / ".plm-runtime-processes"
    try:
        directory.lstat()
    except FileNotFoundError:
        return ()
    _checked_directory(directory)
    records = []
    entries = sorted(directory.iterdir(), key=lambda path: path.name)
    if len(entries) > 64:
        raise WindowsMarkerReconciliationError()
    for path in entries:
        filename = _FILE_NAME.fullmatch(path.name)
        info = path.lstat()
        if (filename is None or not stat.S_ISREG(info.st_mode)
                or stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & _REPARSE
                or not 0 < info.st_size <= 2048):
            raise WindowsMarkerReconciliationError()
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                raise WindowsMarkerReconciliationError()
            payload = stream.read(2049)
        if len(payload) != info.st_size:
            raise WindowsMarkerReconciliationError()
        record = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_fields)
        if (type(record) is not dict or frozenset(record) != _FIELDS
                or type(record["schema_version"]) is not int
                or record["schema_version"] != 1
                or type(record["pid"]) is not int or record["pid"] <= 0
                or type(record["role"]) is not str
                or record["role"] not in _ROLE_ENTRY
                or type(record["nonce"]) is not str
                or not re.fullmatch(r"[a-f0-9]{32}", record["nonce"])
                or filename.groups() != (record["role"].lower(),
                                         str(record["pid"]), record["nonce"])):
            raise WindowsMarkerReconciliationError()
        for key in ("registered_at_utc", "package_version", "code_sha256",
                    "owner_sid", "executable_path"):
            if type(record[key]) is not str or not record[key]:
                raise WindowsMarkerReconciliationError()
        _utc_time(record["registered_at_utc"])
        executable = PureWindowsPath(record["executable_path"])
        if (not _SID.fullmatch(record["owner_sid"])
                or not _SHA.fullmatch(record["code_sha256"])
                or not executable.is_absolute() or executable.drive.startswith("\\\\")):
            raise WindowsMarkerReconciliationError()
        records.append(record)
    return tuple(records)


def reconcile_runtime_markers(data_root: Path, observations: tuple[ProcessObservation, ...],
                              candidates: ProcessAssessment) -> MarkerAssessment:
    """Cross-check observed state without granting any maintenance authority."""
    if (type(observations) is not tuple or type(candidates) is not ProcessAssessment
            or candidates.classification != "DIAGNOSTIC_ONLY"):
        raise WindowsMarkerReconciliationError()
    try:
        records = _read_markers(data_root)
        version = metadata.version("plm-project-tool-backend")
        if version != __version__:
            raise WindowsMarkerReconciliationError()
        package_root = Path(__file__).resolve(strict=True).parents[3]
        digest = package_code_digest(package_root)
        by_pid = {process.pid: process for process in observations}
        if len(by_pid) != len(observations):
            raise WindowsMarkerReconciliationError()
        candidate_pids = {item.pid for item in candidates.findings}
        marker_pids = {item["pid"] for item in records}
        findings = []
        for record in records:
            pid = record["pid"]
            process = by_pid.get(pid)
            if sum(item["pid"] == pid for item in records) > 1:
                status = "CONFLICTING_MARKERS"
            elif process is None:
                status = "PID_NOT_OBSERVED"
            elif (process.owner_sid is None or process.executable_path is None
                  or process.command_line is None or process.created_at_utc is None):
                status = "OS_IDENTITY_UNREADABLE"
            elif (record["package_version"] != version
                  or record["code_sha256"] != digest
                  or process.owner_sid != record["owner_sid"]
                  or PureWindowsPath(process.executable_path) != PureWindowsPath(record["executable_path"])
                  or _utc_time(process.created_at_utc)
                     > _utc_time(record["registered_at_utc"])
                  or not _ROLE_ENTRY[record["role"]].search(process.command_line)
                  or pid not in candidate_pids):
                status = "IDENTITY_MISMATCH"
            else:
                status = "OBSERVED_MATCH"
            findings.append(MarkerFinding(pid, record["role"], status))
        return MarkerAssessment(tuple(findings), tuple(sorted(candidate_pids - marker_pids)))
    except Exception:
        raise WindowsMarkerReconciliationError() from None
