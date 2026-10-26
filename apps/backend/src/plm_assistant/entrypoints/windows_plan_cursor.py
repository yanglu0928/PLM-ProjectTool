"""Fail-closed current-account Vault key for Plan list signatures."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.plan.api.list_cursor import PlanListCursorCodec
from plm_assistant.modules.plan.api.wbs_list_cursor import PlanVersionWbsCursorCodec
from plm_assistant.modules.plan.api.version_list_cursor import PlanVersionListCursorCodec


PLAN_LIST_CURSOR_KEY_REF = "project-plan-list-cursor-v1"


class PlanCursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionPlanCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Plan list cursor key unavailable")


def create_windows_plan_list_cursor_codec(
    *, resolver: PlanCursorKeyResolverPort | None = None,
) -> PlanListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            PLAN_LIST_CURSOR_KEY_REF)
        return PlanListCursorCodec(key)
    except Exception:
        raise ProductionPlanCursorStartupError() from None


def create_windows_plan_version_wbs_cursor_codec(
    *, resolver: PlanCursorKeyResolverPort | None = None,
) -> PlanVersionWbsCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            PLAN_LIST_CURSOR_KEY_REF)
        return PlanVersionWbsCursorCodec(key)
    except Exception:
        raise ProductionPlanCursorStartupError() from None


def create_windows_plan_version_list_cursor_codec(
    *, resolver: PlanCursorKeyResolverPort | None = None,
) -> PlanVersionListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            PLAN_LIST_CURSOR_KEY_REF)
        return PlanVersionListCursorCodec(key)
    except Exception:
        raise ProductionPlanCursorStartupError() from None
