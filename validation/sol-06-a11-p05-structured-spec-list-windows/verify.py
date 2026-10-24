"""Win11 disposable PG/ASGI proof for SOL_SPEC_LIST Windows composition."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError,
    create_windows_structured_spec_list_router,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.solution.api.structured_spec_list_cursor import (
    StructuredSpecListCursorCodec,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_windows_create_for_list",
    ROOT / "validation/sol-06-a09-p05-structured-spec-windows/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_list(*, app, project, other_project, token,
            member_token, first, member, license_guard) -> None:
    path = f"/api/v1/projects/{project}/structured-solution-specs"
    headers = {"cookie": "plm_session=" + token.hex(),
               "origin": "https://plm.example.test"}
    member_headers = {**headers, "cookie": "plm_session=" + member_token.hex()}
    first_page = app.get(path + "?page_size=1", headers=headers)
    assert first_page.status_code == 200, first_page.text
    assert first_page.headers["cache-control"] == "no-store"
    payload = first_page.json()["data"]
    assert payload["has_more"] and len(payload["items"]) == 1
    cursor = payload["next_cursor"]
    second_page = app.get(
        path, params={"page_size": "1", "cursor": cursor}, headers=headers)
    assert second_page.status_code == 200, second_page.text
    assert not second_page.json()["data"]["has_more"]
    listed = payload["items"] + second_page.json()["data"]["items"]
    assert {item["structured_solution_spec_id"] for item in listed} == {
        first["structured_solution_spec_id"], member["structured_solution_spec_id"]}
    assert all(item["project_id"] == str(project)
               and item["version_state"] == "DRAFT" for item in listed)
    assert app.get(path, headers=member_headers).status_code == 200
    assert app.get(path.replace(str(project), str(other_project)),
                   headers=headers).status_code == 404
    assert app.get(path, headers={"origin": headers["origin"]}).status_code == 401
    assert app.get(path + "?unknown=1", headers=headers).status_code == 400
    original = license_guard.require_valid

    def denied(*, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")

    license_guard.require_valid = denied
    try:
        assert app.get(path, headers=headers).status_code == 403
    finally:
        license_guard.require_valid = original
    print("SOL_06_A11_P05_LIST_WINDOWS_HTTP_PG_PASS: real CREATE-to-LIST, "
          "two signed pages, member, cross-project/session/license/query denied")


def on_http(**kwargs) -> None:
    try:
        create_windows_structured_spec_list_router(
            runtime=kwargs["runtime"], sessions=object(), origins=object(),
            license_guard=kwargs["license_guard"], cursors=None)
    except ProductionSolutionOutlineStartupError:
        pass
    else:
        raise AssertionError("missing cursor mounted SOL_SPEC_LIST")
    prior.on_http(
        **kwargs,
        list_router_factory=create_windows_structured_spec_list_router,
        list_cursors=StructuredSpecListCursorCodec(b"l" * 32),
        on_read=lambda **created: on_list(
            **created, license_guard=kwargs["license_guard"]))


if __name__ == "__main__":
    prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.on_created(
        **kwargs, on_http=on_http))
