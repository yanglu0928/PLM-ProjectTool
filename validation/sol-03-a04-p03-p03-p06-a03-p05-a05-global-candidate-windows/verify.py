"""Win11 disposable PG18 proof for explicit GLOBAL candidate factory."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_reference import (
    ProductionSolutionReferenceStartupError,
    create_windows_project_global_reference_candidate_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.solution.application.global_reference_candidate_cursor import (
    GlobalReferenceCandidateCursorCodec,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_candidate_http_fixture",
    ROOT / "validation/sol-03-a04-p03-p03-p06-a03-p05-a04-global-candidate-http/verify.py")
assert SPEC and SPEC.loader
http_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(http_fixture)


def on_http(**facts) -> None:
    dependencies = dict(
        runtime=facts["runtime"], sessions=http_fixture.Sessions(),
        origins=LoginOriginPolicy(["https://plm.example.test"]),
        license_guard=facts["license_guard"],
        cursors=GlobalReferenceCandidateCursorCodec(b"k" * 32),
        document_storage_root=facts["document_storage_root"],
        parse_result_storage_root=facts["parse_result_storage_root"],
    )
    for key in dependencies:
        try:
            create_windows_project_global_reference_candidate_router(
                **{**dependencies, key: None})
        except ProductionSolutionReferenceStartupError:
            pass
        else:
            raise AssertionError(f"candidate factory accepted missing {key}")
    router = create_windows_project_global_reference_candidate_router(**dependencies)
    http_fixture.on_http(**facts, router_override=router)


def on_qualified(**facts) -> None:
    http_fixture.owner_fixture.internal.on_qualified(
        **facts, on_published=lambda **published:
        http_fixture.owner_fixture.on_published(
            **published, on_http=on_http))


if __name__ == "__main__":
    http_fixture.fixture.main(on_qualified=on_qualified)
    print("SOL_03_A04_P03_P03_P06_A03_P05_A05_GLOBAL_CANDIDATE_WINDOWS_PG_PASS")
