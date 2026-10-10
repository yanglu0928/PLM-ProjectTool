"""Disposable Windows Edge/PG proof for two distinct synthetic GLOBAL sources."""

from __future__ import annotations

import hashlib
import importlib.util
import uuid
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "single_global_attestation_browser",
    ROOT / "validation/sol-01-a04-p08-p04-p03-global-attestation-browser/serve.py")
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def second_source(*, port: int, scratch: Path, actor: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    content = b"Synthetic second GLOBAL Reference source; no customer data."
    digest = hashlib.sha256(content).digest()
    file_id = uuid.uuid4()
    stage, locator = LocalFileStorage.locators(
        scope="GLOBAL", project_id=None, file_object_id=file_id)
    storage = LocalFileStorage(scratch / "private-documents")
    with storage.reserve_staging(stage) as stream:
        stream.write(content)
    storage.publish_verified(stage, locator, expected_sha256=digest,
                             expected_size=len(content), max_bytes=100_000_000)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        document = db.execute(
            "INSERT INTO plm.doc_documents(scope,document_category,title,"
            "original_display_name,created_by) VALUES "
            "('GLOBAL','REFERENCE_MATERIAL','Synthetic Second Reference','synthetic-second.txt',%s) "
            "RETURNING document_id", (actor,),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO plm.doc_file_objects(file_object_id,scope,storage_class,"
            "storage_locator,original_name_metadata,created_by,file_state,sha256,"
            "size_bytes,detected_mime,available_at) VALUES "
            "(%s,'GLOBAL','PERSISTENT',%s,'synthetic-second.txt',%s,'AVAILABLE',%s,%s,"
            "'text/plain',statement_timestamp())",
            (file_id, locator, actor, digest, len(content)),
        )
        version = db.execute(
            "INSERT INTO plm.doc_document_versions(document_id,scope,version_no,"
            "file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,"
            "created_by) VALUES (%s,'GLOBAL',1,%s,%s,%s,'text/plain',%s,%s) "
            "RETURNING document_version_id",
            (document, file_id, digest, len(content), Jsonb({}), actor),
        ).fetchone()[0]
        db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,"
                   "effective_version_ref=%s WHERE document_id=%s",
                   (version, version, document))
        evidence = db.execute(
            "INSERT INTO plm.evd_evidence_records(scope,document_id,"
            "document_version_id,locator_type,locator_payload,content_fingerprint,"
            "display_label,created_by) VALUES "
            "('GLOBAL',%s,%s,'DOCUMENT',%s,%s,'Synthetic Second Reference',%s) "
            "RETURNING evidence_id",
            (document, version, Jsonb({"locator_type": "DOCUMENT"}), digest, actor),
        ).fetchone()[0]
        db.execute(
            "UPDATE plm.evd_evidence_records SET eligibility_state='ELIGIBLE',"
            "eligibility_reason='Synthetic review',updated_by=%s,"
            "lock_version=lock_version+1 WHERE evidence_id=%s",
            (actor, evidence),
        )
    return document, version, evidence


def on_preview(**kwargs) -> None:
    document, version, evidence = second_source(
        port=kwargs["port"], scratch=kwargs["scratch"], actor=kwargs["actor"])
    base.on_preview(**kwargs,
                    browser_script=Path(__file__).with_name("run-edge-browser.mjs"),
                    browser_extra=(document, version, evidence))


def main() -> None:
    clear = bytearray(base.PASSWORD.encode("ascii"))
    try:
        with memoryview(clear) as view:
            credential = ScryptPasswordHasher().hash_password(view)
    finally:
        clear[:] = b"\x00" * len(clear)
    base.fixture.main(on_preview=on_preview, login_credential=credential)
    print("SOL_01_A04_P08_P05_P03_GLOBAL_MULTISOURCE_EDGE_PG_PASS: synthetic Windows 11 Edge")


if __name__ == "__main__":
    main()
