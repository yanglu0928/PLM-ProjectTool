"""Windows 11/PostgreSQL 18 proof for RequirementRelation schema."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(
    str(ROOT / "validation/ai-02-a02-model-create/verify.py")
)
connect = helpers["connect"]
definition = runpy.run_path(
    str(ROOT / "validation/sur-01-a02-definition-schema/verify.py")
)
seed_dependencies = definition["seed_dependencies"]


def rejected(action, message: str) -> None:
    try:
        action()
    except Exception:
        return
    raise AssertionError(message)


def main() -> None:
    database = "req01a09a02_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(database)
        ))
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin",
            host="127.0.0.1", port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, "20261007_0120")
        command.upgrade(cfg, "20261007_0121")
        command.downgrade(cfg, "20261007_0120")
        command.upgrade(cfg, "20261007_0121")
        command.check(cfg)

        with connect(database) as db:
            ids = seed_dependencies(db)
            roots = [uuid.uuid4() for _ in range(4)]
            versions = [uuid.uuid4() for _ in range(4)]
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                for ordinal, (root, version) in enumerate(
                        zip(roots, versions, strict=True), 1):
                    code = f"REQ-REL-{ordinal}"
                    db.execute(
                        "INSERT INTO plm.req_requirements(requirement_id,project_id,"
                        "requirement_code,requirement_code_normalized,created_by) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (root, ids["project"], code, code, ids["actor"]),
                    )
                    db.execute(
                        "INSERT INTO plm.req_requirement_versions("
                        "requirement_version_id,requirement_id,project_id,version_no,"
                        "title,statement,rationale,domain_name,priority,risk,"
                        "requirement_classification,content_fingerprint,"
                        "declared_source_count,declared_acceptance_count,"
                        "declared_capability_count,declared_assumption_count,"
                        "declared_exclusion_count,declared_dependency_count,"
                        "declared_ai_task_count,created_by) VALUES ("
                        "%s,%s,%s,1,NULL,'Statement','Rationale','PLM','HIGH','MEDIUM',"
                        "'PENDING_CONFIRMATION',%s,1,0,0,0,0,0,0,%s)",
                        (version, root, ids["project"], bytes([ordinal]) * 32,
                         ids["actor"]),
                    )
                db.execute("SET LOCAL session_replication_role='origin'")

            relation1 = db.execute(
                "INSERT INTO plm.req_relations(project_id,source_requirement_id,"
                "source_requirement_version_id,target_requirement_id,"
                "target_requirement_version_id,relation_type,created_by) "
                "VALUES (%s,%s,%s,%s,%s,'DEPENDS_ON',%s) "
                "RETURNING requirement_relation_id",
                (ids["project"], roots[0], versions[0], roots[1], versions[1],
                 ids["actor"]),
            ).fetchone()[0]
            rejected(lambda: db.execute(
                "INSERT INTO plm.req_relations(project_id,source_requirement_id,"
                "source_requirement_version_id,target_requirement_id,"
                "target_requirement_version_id,relation_type,created_by) "
                "VALUES (%s,%s,%s,%s,%s,'DEPENDS_ON',%s)",
                (ids["project"], roots[0], versions[0], roots[1], versions[1],
                 ids["actor"]),
            ), "duplicate ACTIVE edge accepted")
            rejected(lambda: db.execute(
                "INSERT INTO plm.req_relations(project_id,source_requirement_id,"
                "source_requirement_version_id,target_requirement_id,"
                "target_requirement_version_id,relation_type,created_by) "
                "VALUES (%s,%s,%s,%s,%s,'PARENT_OF',%s)",
                (ids["project"], roots[0], versions[0], roots[0], versions[0],
                 ids["actor"]),
            ), "self edge accepted")
            rejected(lambda: db.execute(
                "INSERT INTO plm.req_relations(project_id,source_requirement_id,"
                "source_requirement_version_id,target_requirement_id,"
                "target_requirement_version_id,relation_type,created_by) "
                "VALUES (%s,%s,%s,%s,%s,'DEPENDS_ON',%s)",
                (uuid.uuid4(), roots[0], versions[0], roots[1], versions[1],
                 ids["actor"]),
            ), "cross-project endpoint accepted")

            left = min(
                ((roots[2], versions[2]), (roots[3], versions[3])),
                key=lambda pair: (pair[0].bytes, pair[1].bytes),
            )
            right = max(
                ((roots[2], versions[2]), (roots[3], versions[3])),
                key=lambda pair: (pair[0].bytes, pair[1].bytes),
            )
            rejected(lambda: db.execute(
                "INSERT INTO plm.req_relations(project_id,source_requirement_id,"
                "source_requirement_version_id,target_requirement_id,"
                "target_requirement_version_id,relation_type,created_by) "
                "VALUES (%s,%s,%s,%s,%s,'DUPLICATES',%s)",
                (ids["project"], right[0], right[1], left[0], left[1],
                 ids["actor"]),
            ), "noncanonical symmetric edge accepted")
            symmetric = db.execute(
                "INSERT INTO plm.req_relations(project_id,source_requirement_id,"
                "source_requirement_version_id,target_requirement_id,"
                "target_requirement_version_id,relation_type,created_by) "
                "VALUES (%s,%s,%s,%s,%s,'DUPLICATES',%s) "
                "RETURNING requirement_relation_id",
                (ids["project"], left[0], left[1], right[0], right[1],
                 ids["actor"]),
            ).fetchone()[0]

            replacement = db.execute(
                "INSERT INTO plm.req_relations(project_id,source_requirement_id,"
                "source_requirement_version_id,target_requirement_id,"
                "target_requirement_version_id,relation_type,created_by) "
                "VALUES (%s,%s,%s,%s,%s,'RELATED_TO',%s) "
                "RETURNING requirement_relation_id",
                (ids["project"], roots[1], versions[1], roots[2], versions[2],
                 ids["actor"]),
            ).fetchone()[0]
            db.execute(
                "UPDATE plm.req_relations SET relation_state='SUPERSEDED',"
                "lock_version=1,superseded_by_ref=%s WHERE requirement_relation_id=%s",
                (replacement, relation1),
            )
            db.execute(
                "UPDATE plm.req_relations SET relation_state='REVOKED',lock_version=1 "
                "WHERE requirement_relation_id=%s", (symmetric,),
            )
            rejected(lambda: db.execute(
                "UPDATE plm.req_relations SET relation_state='ACTIVE',lock_version=0 "
                "WHERE requirement_relation_id=%s", (symmetric,),
            ), "terminal relation restored")
            rejected(lambda: db.execute(
                "UPDATE plm.req_relations SET relation_type='PARENT_OF' "
                "WHERE requirement_relation_id=%s", (replacement,),
            ), "active relation content rewritten")
            rejected(lambda: db.execute(
                "DELETE FROM plm.req_relations WHERE requirement_relation_id=%s",
                (replacement,),
            ), "relation deleted")
            rejected(lambda: db.execute(
                "TRUNCATE plm.req_relations",
            ), "relation history truncated")

        rejected(
            lambda: command.downgrade(cfg, "20261007_0120"),
            "relation history allowed downgrade",
        )
        command.check(cfg)
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(database)
            ))
    print(
        "REQ_01_A09_A02_RELATION_SCHEMA_PASS: migration, same-project fixed "
        "versions, active uniqueness, symmetric order, irreversible lifecycle, "
        "delete/truncate refusal, downgrade and drift verified on Windows 11/"
        "PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
