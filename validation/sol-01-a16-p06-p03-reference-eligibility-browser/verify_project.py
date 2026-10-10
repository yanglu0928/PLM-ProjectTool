"""Disposable Win11 Edge/PG18 PROJECT Reference eligibility UI proof."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_reference_browser_base",
    ROOT / "validation/sol-01-a12-p03-project-reference-revise-browser/serve.py")
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def on_created(**facts) -> None:
    base.on_created(
        **facts, browser_script=Path(__file__).with_name("run-project-edge.mjs"),
        include_eligibility=True, expect_revision=False)
    root = facts["created"].reference_solution_id
    with psycopg.connect(host="127.0.0.1", port=facts["port"], user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT eligibility_state,lock_version FROM plm.sol_reference_solutions "
            "WHERE reference_solution_id=%s", (root,)).fetchone() == ("RESTRICTED", 2)
        assert db.execute(
            "SELECT count(*) FROM plm.sol_reference_eligibility_events "
            "WHERE reference_solution_id=%s", (root,)).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events "
            "WHERE action='SOL_REFERENCE_ELIGIBILITY_SET' AND target_object_id=%s",
            (root,)).fetchone()[0] == 2
    print("SOL_01_A16_P06_P03_PROJECT_ELIGIBILITY_EDGE_PG_PASS")


if __name__ == "__main__":
    base.fixture.main(on_created=on_created)
