"""Win11 disposable PG/ASGI proof for SOL_SPEC_GET Windows composition."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError,
    create_windows_structured_spec_read_router,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_windows_create_for_get",
    ROOT / "validation/sol-06-a09-p05-structured-spec-windows/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_read(*, app, project, other_project, token,
            member_token, first, member) -> None:
    spec = first["structured_solution_spec_id"]
    path = f"/api/v1/projects/{project}/structured-solution-specs/{spec}"
    headers = {"cookie": "plm_session=" + token.hex(),
               "origin": "https://plm.example.test"}
    member_headers = {**headers, "cookie": "plm_session=" + member_token.hex()}
    with TestClient(create_app(), base_url="https://plm.example.test") as closed:
        assert closed.get(path, headers=headers).status_code == 404
    detail = app.get(path, headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"] == first
    assert detail.headers["cache-control"] == "no-store"
    assert detail.headers["x-trace-id"] == detail.json()["trace_id"]
    assert app.get(path, headers=member_headers).status_code == 200
    member_path = f"/api/v1/projects/{project}/structured-solution-specs/" \
                  f"{member['structured_solution_spec_id']}"
    assert app.get(member_path, headers=member_headers).json()["data"] == member
    assert app.get(path.replace(str(project), str(other_project)),
                   headers=headers).status_code == 404
    assert app.get(path, headers={"origin": headers["origin"]}).status_code == 401
    assert app.get(path + "?unknown=1", headers=headers).status_code == 400
    print("SOL_06_A10_P03_GET_WINDOWS_HTTP_PG_PASS: real create-to-read, "
          "member read, default closed, cross-project/session/query denied")


def on_http(**kwargs) -> None:
    try:
        create_windows_structured_spec_read_router(
            runtime=kwargs["runtime"], sessions=None,
            origins=object(), license_guard=kwargs["license_guard"])
    except ProductionSolutionOutlineStartupError:
        pass
    else:
        raise AssertionError("missing Session mounted SOL_SPEC_GET")
    prior.on_http(
        **kwargs, read_router_factory=create_windows_structured_spec_read_router,
        on_read=on_read)


if __name__ == "__main__":
    prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.on_created(
        **kwargs, on_http=on_http))
