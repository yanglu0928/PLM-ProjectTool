from __future__ import annotations

import json
import re
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import TextIO


_SAFE_LABEL = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
_SAFE_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_APPLICATION_EVENTS = {"app_started", "app_stopped", "request_failed"}
_INTEGRATION_EVENTS = {"integration_finished"}
_INTEGRATION_TYPES = {"ai", "ocr", "plugin", "file_conversion"}
_PROVIDERS = {
    "bailian", "deepseek", "paddleocr", "tesseract", "ghostscript",
    "office", "plugin", "unknown",
}


def _label(value: str) -> str:
    if not isinstance(value, str) or _SAFE_LABEL.fullmatch(value) is None:
        raise ValueError("unsafe log label")
    return value


def _trace(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        if str(uuid.UUID(value)) == value:
            return value
    except (ValueError, TypeError, AttributeError):
        pass
    raise ValueError("invalid trace id")


class StructuredLoggers:
    """Separate, allowlisted JSON streams; never accept arbitrary messages."""

    def __init__(
        self,
        *,
        application_stream: TextIO | None = None,
        integration_stream: TextIO | None = None,
    ) -> None:
        self._application_stream = application_stream or sys.stdout
        self._integration_stream = integration_stream or sys.stderr
        self._lock = threading.Lock()

    def _write(self, stream: TextIO, record: dict[str, object]) -> None:
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            stream.write(line + "\n")
            stream.flush()

    def application(
        self,
        *,
        event: str,
        component: str,
        level: str = "INFO",
        trace_id: str | None = None,
        error_code: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        if event not in _APPLICATION_EVENTS:
            raise ValueError("unregistered application log event")
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ValueError("invalid log level")
        if error_code is not None and _SAFE_CODE.fullmatch(error_code) is None:
            raise ValueError("unsafe error code")
        if duration_ms is not None and (type(duration_ms) is not int or duration_ms < 0):
            raise ValueError("invalid duration")
        record: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "category": "application",
            "level": level,
            "component": _label(component),
            "event": _label(event),
        }
        for key, value in (
            ("trace_id", _trace(trace_id)),
            ("error_code", error_code),
            ("duration_ms", duration_ms),
        ):
            if value is not None:
                record[key] = value
        self._write(self._application_stream, record)

    def integration(
        self,
        *,
        event: str,
        integration_type: str,
        provider: str,
        trace_id: str,
        outcome: str,
        duration_ms: int,
        retryable: bool,
        invocation_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        if event not in _INTEGRATION_EVENTS:
            raise ValueError("unregistered integration log event")
        if integration_type not in _INTEGRATION_TYPES or provider not in _PROVIDERS:
            raise ValueError("unregistered integration identity")
        if outcome not in {"SUCCESS", "FAILURE"} or type(retryable) is not bool:
            raise ValueError("invalid integration outcome")
        if type(duration_ms) is not int or duration_ms < 0:
            raise ValueError("invalid duration")
        if error_code is not None and _SAFE_CODE.fullmatch(error_code) is None:
            raise ValueError("unsafe error code")
        record: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "category": "integration",
            "level": "INFO" if outcome == "SUCCESS" else "WARNING",
            "event": _label(event),
            "integration_type": _label(integration_type),
            "provider": _label(provider),
            "trace_id": _trace(trace_id),
            "outcome": outcome,
            "duration_ms": duration_ms,
            "retryable": retryable,
        }
        if invocation_id is not None:
            record["invocation_id"] = _trace(invocation_id)
        if error_code is not None:
            record["error_code"] = error_code
        self._write(self._integration_stream, record)
