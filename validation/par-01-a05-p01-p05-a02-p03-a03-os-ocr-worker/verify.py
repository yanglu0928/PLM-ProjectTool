"""Spawned Windows process: committed synthetic scanned PDF -> real local OCR."""

from __future__ import annotations

import io
import json
import multiprocessing
import os
import uuid
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from plm_assistant.entrypoints.parser_worker_windows import create_windows_parser_worker
from plm_assistant.entrypoints.parser_worker_signals import run_parser_worker_process
from plm_assistant.modules.document.infrastructure.parse_result_storage import LocalParseResultStorage
from plm_assistant.modules.parser.infrastructure.paddle_ocr import _model_fingerprint
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings


spec = spec_from_file_location("_parser_os_fixture",
    Path(__file__).resolve().parents[1] /
    "par-01-a05-p01-p04-p03-p02-cancel-owner" / "verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)
fixture.fixture.PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))


class Guard:
    def require_valid(self, *, trace_id):
        return object()  # Synthetic trust only; not a formal license proof.


def worker_child(url, root, actor_id, det, rec, fingerprint, output):
    database = loop = None
    try:
        settings = BootstrapSettings(data_root=Path(root),
            parser_ocr_detection_model_dir=Path(det),
            parser_ocr_recognition_model_dir=Path(rec),
            parser_ocr_model_fingerprint=fingerprint)
        actor = SimpleNamespace(assert_current=lambda: actor_id)
        with patch("plm_assistant.entrypoints.parser_worker_windows.read_database_url",
                   return_value=url), \
             patch("plm_assistant.entrypoints.parser_worker_windows.create_windows_worker_license_services",
                   return_value=SimpleNamespace(guard=Guard())), \
             patch("plm_assistant.entrypoints.parser_worker_windows.create_windows_system_actor",
                   return_value=actor):
            database, loop = create_windows_parser_worker(settings)
        result = run_parser_worker_process(loop, max_cycles=1)
        with loop.quiescent():
            database.dispose()
        database = None
        output.put((result.reason, result.published, None))
    except Exception as exc:
        output.put((None, None, type(exc).__name__ + ":" + str(exc)))
    finally:
        if database is not None and loop is not None:
            try:
                with loop.quiescent():
                    database.dispose()
            except Exception:
                pass


def scanned_pdf(font_path: Path) -> bytes:
    image = Image.new("RGB", (1000, 220), "white")
    ImageDraw.Draw(image).text((30, 45), "PROJECT SCOPE APPROVED",
        font=ImageFont.truetype(str(font_path), 48), fill="black")
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    with pymupdf.open() as document:
        document.new_page().insert_image(pymupdf.Rect(40, 40, 540, 150),
                                          stream=stream.getvalue())
        return document.tobytes()


def exercise(v):
    det = Path(os.environ["PLM_TEST_OCR_DET_MODEL_DIR"])
    rec = Path(os.environ["PLM_TEST_OCR_REC_MODEL_DIR"])
    font = Path(os.environ["PLM_TEST_OCR_FONT"])
    fingerprint = _model_fingerprint(det, rec)  # Test fixture only, not trust manifest.

    def extra(v, *, db, client, lease, headers, path, body, snapshot):
        content = scanned_pdf(font)
        upload, _, _ = v["seed"](content)
        request = replace(v["cmd"], upload_id=upload, trace_id=uuid.uuid4(),
                          max_bytes=len(content))
        ref = v["worker"].commit(request,
            idempotency_key="synthetic-parser-os-ocr")
        context = multiprocessing.get_context("spawn")
        rejected = context.SimpleQueue()
        bad_process = context.Process(target=worker_child, args=(v["url"],
            str(v["root"]), v["actor"], str(det), str(rec), "0" * 64, rejected))
        bad_process.start()
        bad_process.join(30)
        if bad_process.is_alive():
            bad_process.terminate()
            bad_process.join(5)
            raise AssertionError("synthetic invalid-model child timed out")
        assert bad_process.exitcode == 0, bad_process.exitcode
        bad_reason, bad_published, bad_error = rejected.get()
        assert bad_reason is None and bad_published is None and bad_error is not None
        assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
            (ref.parse_job_id,)).fetchone()[0] == "PENDING"
        output = context.SimpleQueue()
        process = context.Process(target=worker_child, args=(v["url"],
            str(v["root"]), v["actor"], str(det), str(rec), fingerprint, output))
        process.start()
        process.join(90)
        if process.is_alive():
            process.terminate()  # Synthetic test cleanup only, never production stop.
            process.join(5)
            raise AssertionError("synthetic Parser child timed out")
        assert process.exitcode == 0, process.exitcode
        reason, published, error = output.get()
        assert error is None, error
        assert (reason, published) == ("LIMIT", 1), (reason, published)
        assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
            (ref.parse_job_id,)).fetchone()[0] == "SUCCEEDED"
        row = db.execute("SELECT r.parse_result_ref_id,r.storage_locator,r.sha256,"
            "r.size_bytes FROM plm.doc_parse_result_refs r JOIN plm.doc_parse_records p "
            "ON p.parse_record_id=r.parse_record_id WHERE p.job_ref=%s",
            (ref.parse_job_id,)).fetchone()
        assert row is not None
        raw = LocalParseResultStorage(v["root"]).read_verified(
            scope="PROJECT", project_id=v["project"], result_ref_id=row[0],
            expected_locator=row[1], expected_sha256=row[2], expected_size=row[3])
        parsed = json.loads(raw)
        assert parsed["ocr_model_fingerprint"] == fingerprint
        assert any(node["kind"] == "OCR_LINE" and
                   node["text"] == "PROJECT SCOPE APPROVED"
                   for node in parsed["nodes"]), parsed["nodes"]
        print("PAR-01-A05-P01-P05-A02-P03-A03: independent Windows process, "
              "actual local model/scanned PDF, unique verified OCR result PASS")

    fixture.exercise(v, extra=extra)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    fixture.fixture.verify(exercise=exercise)
