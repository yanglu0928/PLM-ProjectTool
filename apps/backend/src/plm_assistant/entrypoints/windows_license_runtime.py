"""Fail-closed Windows composition of the internal License trust chain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from plm_assistant.entrypoints.production_login import _schema_current
from plm_assistant.entrypoints.windows_trusted_time import create_windows_trusted_time_integrity
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.license.application.license_validation import LicenseService
from plm_assistant.modules.license.application.runtime_guard import LicenseRuntimeGuard
from plm_assistant.modules.license.application.signature_verifier import LicenseSignatureVerifier
from plm_assistant.modules.license.application.trusted_time import TrustedTimeStatePort
from plm_assistant.modules.license.infrastructure.packaged_product_key import PackagedProductKey
from plm_assistant.modules.license.infrastructure.runtime_guard_repository import (
    SqlAlchemyRuntimeLicenseRepository,
)
from plm_assistant.modules.license.infrastructure.trusted_time_repository import (
    SqlAlchemyTrustedTimeRepository,
)
from plm_assistant.modules.license.infrastructure.windows_selected_machine import WindowsSelectedMachine
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime


class ProductionLicenseStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("production license unavailable")


class _SystemClock:
    @staticmethod
    def now_utc() -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class WindowsLicenseServices:
    validator: LicenseService
    trusted_time: TrustedTimeStatePort
    guard: LicenseRuntimeGuard


def _assemble(runtime: DatabaseRuntime, *, product: object, machine: object,
              integrity: object) -> WindowsLicenseServices:
    """Shared wiring for production and isolated synthetic integration checks."""
    audit = AuditService(SqlAlchemyAuditRepository())
    trusted = TrustedTimeStatePort(
        runtime.unit_of_work, SqlAlchemyTrustedTimeRepository(), integrity, audit,
    )
    clock = _SystemClock()
    validator = LicenseService(
        LicenseSignatureVerifier(product), machine, product, clock, trusted,
    )
    guard = LicenseRuntimeGuard(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyRuntimeLicenseRepository(), validator=validator,
        trusted_time=trusted, audit=audit, clock=clock.now_utc,
    )
    return WindowsLicenseServices(validator, trusted, guard)


def create_windows_license_services(
    runtime: DatabaseRuntime, settings: BootstrapSettings,
) -> WindowsLicenseServices:
    """Never accept request/config/DB-supplied trust roots or test substitutes."""
    if not isinstance(runtime, DatabaseRuntime) or not isinstance(settings, BootstrapSettings):
        raise ProductionLicenseStartupError()
    try:
        if not runtime.is_ready() or not _schema_current(runtime):
            raise ProductionLicenseStartupError()
        product = PackagedProductKey()
        machine = WindowsSelectedMachine(settings.selected_mac)
        machine.selected_mac()
        integrity = create_windows_trusted_time_integrity()
        return _assemble(runtime, product=product, machine=machine, integrity=integrity)
    except Exception:
        raise ProductionLicenseStartupError() from None
