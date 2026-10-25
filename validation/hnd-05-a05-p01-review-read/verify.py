"""Windows 11 isolated PG/HTTP proof of current HND-02 Review GET ownership."""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import Mock

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_project_review import (
    create_windows_project_review_read_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.handover.infrastructure.review_subject_repository import (
    SqlAlchemyHandoverReviewSubjectRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation/hnd-01-a04-a02-p02-review-owner/verify.py"
spec = importlib.util.spec_from_file_location("hnd_review_read_fixture", SOURCE)
assert spec is not None and spec.loader is not None
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def probe(**ctx) -> None:
    router = create_windows_project_review_read_router(
        ctx["runtime"], origins=LoginOriginPolicy(["http://localhost"]),
        license_guard=ctx["guard"], audit=ctx["audit"],
        documents=Mock(), downloads=Mock(), parse_results=Mock(),
    )
    path = f"/api/v1/projects/{ctx['project']}/reviews/{ctx['review_id']}"
    headers = lambda token: {"cookie": "plm_session=" + token.hex()}
    with TestClient(create_app(review_read_router=router),
                    base_url="http://localhost") as client:
        for token in (ctx["manager_token"], ctx["reviewer_token"]):
            response = client.get(path, headers=headers(token))
            assert response.status_code == 200, response.text
            data = response.json()["data"]
            assert data["subject_ref"] == {
                "resource_type": "HND-02",
                "resource_id": str(ctx["analysis_id"]),
            }, data
            assert data["policy_code"] == "HANDOVER_ALL_V1"
            assert data["active_round"]["subject_version_ref"] == str(ctx["version_id"])
            assert data["active_round"]["review_round_id"] == str(ctx["round_id"])
            assert data["state"] == "IN_REVIEW"
        assert client.get(path).status_code == 401
        assert client.get(
            f"/api/v1/projects/{uuid.uuid4()}/reviews/{ctx['review_id']}",
            headers=headers(ctx["reviewer_token"])).status_code == 404
        repository = SqlAlchemyHandoverReviewSubjectRepository()
        with ctx["runtime"].unit_of_work() as tx:
            assert repository.active_version_exists(
                tx, project_id=ctx["project"],
                analysis_id=ctx["analysis_id"],
                analysis_version_id=ctx["version_id"])
            assert not repository.active_version_exists(
                tx, project_id=ctx["project"],
                analysis_id=ctx["analysis_id"],
                analysis_version_id=uuid.uuid4())
        with fixture.connect(ctx["database"]) as db:
            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                       "lock_version=lock_version+1 WHERE project_id=%s AND user_id=%s",
                       (ctx["project"], ctx["reviewer"]))
        assert client.get(path, headers=headers(ctx["reviewer_token"])).status_code == 404
        with fixture.connect(ctx["database"]) as db:
            db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                       "lock_version=lock_version+1 WHERE project_id=%s AND user_id=%s",
                       (ctx["project"], ctx["reviewer"]))
        assert client.get(path, headers=headers(ctx["reviewer_token"])).status_code == 200
    print("HND_05_A05_P01_REVIEW_READ_PG_HTTP_PASS: current member, exact version, denied access")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path, required=True)
    args = parser.parse_args()
    temp_root = args.temp_root.resolve(strict=True)
    pg = args.pg_bin.resolve(strict=True)
    assert (pg / "initdb.exe").is_file() and (pg / "pg_ctl.exe").is_file()
    run = Path(mkdtemp(prefix="plm-hnd-review-read-", dir=temp_root))
    assert run.resolve(strict=True).parent == temp_root
    data, log = run / "pgdata", run / "postgresql.log"
    env = os.environ.copy()
    env["PATH"] = str(pg) + os.pathsep + env["PATH"]
    started = False
    try:
        subprocess.run([
            str(pg / "initdb.exe"), f"--pgdata={data}",
            "--username=poc_admin", "--auth=trust", "--encoding=UTF8",
            "--locale=C",
        ], env=env, capture_output=True, text=True, check=True, timeout=120)
        subprocess.run([
            str(pg / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
            "-o", "-h 127.0.0.1 -p 55434", "-w", "start",
        ], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=True, timeout=120)
        started = True
        fixture.main(use_http=True, read_probe=probe)
    finally:
        if started:
            subprocess.run([
                str(pg / "pg_ctl.exe"), "-D", str(data), "-m", "fast",
                "-w", "stop",
            ], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=True, timeout=60)
        if run.resolve(strict=True).parent != temp_root or not run.name.startswith(
                "plm-hnd-review-read-"):
            raise RuntimeError("synthetic PG cleanup scope rejected")
        shutil.rmtree(run)
