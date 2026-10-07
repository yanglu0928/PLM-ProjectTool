"""Windows 11/PostgreSQL 18 proof for Requirement production composition."""

from __future__ import annotations

import runpy
from pathlib import Path
from types import SimpleNamespace

from plm_assistant.entrypoints.api import create_app as create_api_app
from plm_assistant.entrypoints.windows_project_review import (
    create_windows_project_review_router,
)
from plm_assistant.entrypoints.windows_requirement import (
    REQUIREMENT_CURSOR_KEY_REF, REQUIREMENT_PACKAGE_CURSOR_KEY_REF,
    REQUIREMENT_RELATION_CURSOR_KEY_REF, REQUIREMENT_VERSION_CURSOR_KEY_REF,
    create_windows_requirement_routers,
)


ROOT = Path(__file__).resolve().parents[2]


class Keys:
    def __init__(self) -> None:
        self.refs: list[str] = []

    def resolve_key(self, key_ref: str) -> bytes:
        self.refs.append(key_ref)
        return {
            REQUIREMENT_PACKAGE_CURSOR_KEY_REF: b"p" * 32,
            REQUIREMENT_CURSOR_KEY_REF: b"q" * 32,
            REQUIREMENT_VERSION_CURSOR_KEY_REF: b"v" * 32,
            REQUIREMENT_RELATION_CURSOR_KEY_REF: b"r" * 32,
        }[key_ref]


def _operations(routers) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    for router in (
        routers.packages, routers.requirements, routers.versions,
        routers.relations, routers.review_submission,
    ):
        if router is not None:
            result.extend(
                (method, route.path)
                for route in router.routes
                for method in route.methods
                if method not in {"HEAD", "OPTIONS"}
            )
    return tuple(result)


def main() -> None:
    package_proof = runpy.run_path(str(
        ROOT / "validation" / "req-01-a10-a03-p02-package-http" / "verify.py"
    ))
    original_app = package_proof["create_app"]
    mounted: dict[str, object] = {}

    def production_package_router(*, sessions, origins, reads, creates,
                                  mutations, cursors):
        del mutations, cursors
        runtime = SimpleNamespace(unit_of_work=reads._uow)
        keys = Keys()
        routers = create_windows_requirement_routers(
            runtime, sessions=sessions, origins=origins,
            license_guard=reads._guard, audit=creates._audit,
            include_write=True, resolver=keys,
        )
        operations = _operations(routers)
        assert len(operations) == 22, operations
        assert sum(method == "GET" for method, _ in operations) == 7
        assert sum(method != "GET" for method, _ in operations) == 15
        assert keys.refs == [
            REQUIREMENT_PACKAGE_CURSOR_KEY_REF, REQUIREMENT_CURSOR_KEY_REF,
            REQUIREMENT_VERSION_CURSOR_KEY_REF,
            REQUIREMENT_RELATION_CURSOR_KEY_REF,
        ]
        mounted.update(
            runtime=runtime, sessions=sessions, origins=origins,
            guard=reads._guard, audit=creates._audit, routers=routers,
        )
        return routers.packages

    def production_app(**kwargs):
        del kwargs
        routers = mounted["routers"]
        review_router = create_windows_project_review_router(
            mounted["runtime"], sessions=mounted["sessions"],
            origins=mounted["origins"], license_guard=mounted["guard"],
            audit=mounted["audit"],
        )
        return create_api_app(
            requirement_package_router=routers.packages,
            requirement_router=routers.requirements,
            requirement_version_router=routers.versions,
            requirement_review_submission_router=routers.review_submission,
            requirement_relation_router=routers.relations,
            review_command_router=review_router,
        )

    proof_globals = package_proof["main"].__globals__
    proof_globals["create_requirement_package_router"] = production_package_router
    proof_globals["create_app"] = production_app
    package_proof["main"]()
    assert mounted, "production Requirement composition was not invoked"
    assert original_app is not production_app
    print("REQ-01-A10-A08 Windows Requirement composition: PASS")


if __name__ == "__main__":
    main()
