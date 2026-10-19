"""Win11 real HTTP/PostgreSQL proof for production REVIEW_LIST composition."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_project_review import (
    create_windows_project_review_list_router,
)
from plm_assistant.entrypoints.windows_review_list_cursor import (
    REVIEW_LIST_CURSOR_KEY_REF,
    create_windows_review_list_cursor_codec,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.review.application.list_contract import (
    ReviewListPosition,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_review_get_for_review_list_windows",
    ROOT / "validation/sol-06-a15-p04-structured-spec-review-get-windows/verify.py",
)
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class _Resolver:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def resolve_key(self, key_ref: str) -> bytes:
        self.calls.append(key_ref)
        return b"r" * 32


def _headers(token: bytes) -> dict[str, str]:
    return {"cookie": "plm_session=" + token.hex()}


def _audit_count(port: int) -> int:
    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as database:
        return database.execute(
            "SELECT count(*) FROM plm.aud_events",
        ).fetchone()[0]


def _list_router(*, runtime, license_guard, audit, documents, downloads,
                 parse_results, codec, **_unused):
    return create_windows_project_review_list_router(
        runtime, origins=LoginOriginPolicy(["https://plm.example.test"]),
        license_guard=license_guard, audit=audit, documents=documents,
        downloads=downloads, parse_results=parse_results, cursors=codec,
    )


def _assert_active_list(
    *, router, codec, **context,
) -> tuple[str, int, uuid.UUID]:
    project = context["project"]
    other_project = context["other_project"]
    token = context["token"]
    member_token = context["member_token"]
    draft = context["draft"]
    review_id, round_id = prior._review_ids(**context)
    path = f"/api/v1/projects/{project}/reviews"
    before = _audit_count(context["port"])

    with TestClient(create_app(), base_url="https://plm.example.test") as closed:
        assert closed.get(path, headers=_headers(token)).status_code == 404
    with TestClient(
        create_app(review_list_router=router),
        base_url="https://plm.example.test",
    ) as application:
        assert application.get(path).status_code == 401
        assert application.get(path, headers=_headers(b"z" * 32)).status_code == 401
        assert application.get(
            path.replace(str(project), str(other_project)),
            headers=_headers(token),
        ).status_code == 404
        assert application.get(
            path + "?unknown=x", headers=_headers(token),
        ).status_code == 400
        assert application.get(
            path + "?cursor=not-a-cursor", headers=_headers(token),
        ).status_code == 400
        foreign_cursor = codec.encode(
            session_token=token, project_id=project, view="my_pending",
            page_size=1,
            position=ReviewListPosition(
                datetime(2026, 10, 19, tzinfo=timezone.utc), uuid.uuid4(),
            ),
        )
        assert application.get(
            path + f"?view=all&page_size=1&cursor={foreign_cursor}",
            headers=_headers(token),
        ).status_code == 400

        manager_all = application.get(path, headers=_headers(token))
        manager_pending = application.get(
            path + "?view=my_pending&page_size=1", headers=_headers(token),
        )
        member_all = application.get(path, headers=_headers(member_token))
        member_pending = application.get(
            path + "?view=my_pending&page_size=1",
            headers=_headers(member_token),
        )
        assert manager_all.status_code == manager_pending.status_code == 200
        assert member_all.status_code == member_pending.status_code == 200
        assert manager_all.headers["cache-control"] == "no-store"
        assert manager_all.headers["x-content-type-options"] == "nosniff"
        manager_items = manager_all.json()["data"]["items"]
        pending_items = manager_pending.json()["data"]["items"]
        member_items = member_all.json()["data"]["items"]
        assert manager_items and pending_items and member_items
        assert member_pending.json()["data"]["items"] == []
        item = next(
            candidate for candidate in manager_items
            if candidate["review_id"] == str(review_id)
        )
        pending_item = next(
            candidate for candidate in pending_items
            if candidate["review_id"] == str(review_id)
        )
        member_item = next(
            candidate for candidate in member_items
            if candidate["review_id"] == str(review_id)
        )
        assert pending_item["active_round"]["my_assignment"]["state"] == "PENDING"
        assert item["review_id"] == str(review_id)
        assert item["project_id"] == str(project)
        assert item["subject_ref"] == {
            "resource_type": "SOL-06", "resource_id": str(draft.spec_series_id),
        }
        assert item["policy_code"] == "STRUCTURED_SPEC_ALL_V1"
        assert item["state"] == "IN_REVIEW" and item["etag"] == '"v1"'
        active = item["active_round"]
        assert active["review_round_id"] == str(round_id)
        assert active["subject_version_ref"] == str(
            draft.structured_solution_spec_id)
        assert active["my_assignment"]["state"] == "PENDING"
        assert active["my_assignment"]["decision"] is None
        assert member_item["active_round"]["my_assignment"] is None

        seen: set[str] = set()
        next_cursor = None
        for _ in range(10):
            suffix = "?page_size=1"
            if next_cursor is not None:
                suffix += "&cursor=" + next_cursor
            page = application.get(path + suffix, headers=_headers(token))
            assert page.status_code == 200, page.text
            data = page.json()["data"]
            assert len(data["items"]) <= 1
            seen.update(row["review_id"] for row in data["items"])
            if not data["has_more"]:
                assert data["next_cursor"] is None
                break
            next_cursor = data["next_cursor"]
            assert isinstance(next_cursor, str) and next_cursor
            assert application.get(
                path + "?page_size=1&cursor=" + next_cursor,
                headers=_headers(member_token),
            ).status_code == 400
        else:
            raise AssertionError("bounded Review pagination did not finish")
        assert str(review_id) in seen and len(seen) >= 2

    denied = _list_router(
        **{**context, "codec": codec,
           "license_guard": prior.prior.prior.DeniedLicense()},
    )
    with TestClient(
        create_app(review_list_router=denied),
        base_url="https://plm.example.test",
    ) as application:
        assert application.get(path, headers=_headers(token)).status_code == 403
    assert _audit_count(context["port"]) == before
    print(
        "SOL_06_A16_P06_ACTIVE_REVIEW_LIST_HTTP_PG_PASS: default closed, "
        "dedicated encrypted cursor binding, manager/member all and actor-only "
        "my_pending projection, project/session/license isolation and zero writes",
    )
    return path, before, review_id


def _assert_terminal_list(
    *, router, path: str, review_id: uuid.UUID, **context,
) -> None:
    audit_before = _audit_count(context["port"])
    with TestClient(
        create_app(review_list_router=router),
        base_url="https://plm.example.test",
    ) as application:
        pending = application.get(
            path + "?view=my_pending", headers=_headers(context["token"]),
        )
        all_reviews = application.get(path, headers=_headers(context["token"]))
        assert pending.status_code == all_reviews.status_code == 200
        assert pending.json()["data"]["items"] == []
        item = next(
            candidate for candidate in all_reviews.json()["data"]["items"]
            if candidate["review_id"] == str(review_id)
        )
        assert item["state"] == "APPROVED"
        assert item["etag"] == '"v2"'
        assert item["active_round"] is None
    assert _audit_count(context["port"]) == audit_before
    print(
        "SOL_06_A16_P06_TERMINAL_REVIEW_LIST_HTTP_PG_PASS: terminal Review "
        "remains in all, leaves my_pending, returns null active_round and "
        "performs zero read writes",
    )


def _after_submit(**context) -> None:
    prior.prior.prior.on_http(**context)
    resolver = _Resolver()
    codec = create_windows_review_list_cursor_codec(resolver=resolver)
    assert resolver.calls == [REVIEW_LIST_CURSOR_KEY_REF]
    router = _list_router(**context, codec=codec)
    path, _before, review_id = _assert_active_list(
        **context, codec=codec, router=router,
    )
    prior.prior._terminal("APPROVE", **context)
    _assert_terminal_list(
        **context, router=router, path=path, review_id=review_id,
    )


def _after_specs(*, created: dict[str, object], **specs) -> None:
    prior.prior.prior.prior.prior.on_trace(
        **specs, csrf=created["csrf"], member_csrf=created["member_csrf"],
        audit=created["audit"], license_guard=created["license_guard"],
        documents=created["documents"], downloads=created["downloads"],
        parse_results=created["parse_results"], evidence=created["evidence"],
        on_review=lambda **review: prior.prior.prior.prior.on_review(
            **review,
            on_submit=lambda **submit: _after_submit(**submit),
        ),
    )


def main() -> None:
    prior.prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        prior.prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            prior.prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                _after_specs(created=created, **specs),
            ),
        ),
    )


if __name__ == "__main__":
    main()
