"""Replay real synthetic native-PDF text locators and reject OCR-only pages."""

from __future__ import annotations

import hashlib
import tempfile
import unicodedata
import uuid
from pathlib import Path

import pymupdf

from plm_assistant.modules.document.application.read_documents import DocumentReadQuery
from plm_assistant.modules.document.application.read_parse_result import VerifiedParseResult
from plm_assistant.modules.evidence.application.parsed_node_proof import ParsedNodeEvidenceProofService
from plm_assistant.modules.parser.application.extract_pdf_text import extract_pdf_text
from plm_assistant.modules.parser.application.prepare_input import VerifiedParserInput
from plm_assistant.modules.parser.application.profile_selection import (
    ParserInputVersion, choose_parser_profile,
)
from plm_assistant.modules.parser.application.structured_result import ParserResultError


class ResultPort:
    def __init__(self, value: VerifiedParseResult) -> None:
        self.value = value

    def read(self, *_args, **_kwargs) -> VerifiedParseResult:
        return self.value


def prepared_file(path: Path):
    raw = path.read_bytes()
    source = ParserInputVersion(uuid.uuid4(), hashlib.sha256(raw).digest(),
                                len(raw), "application/pdf")
    return source, VerifiedParserInput(choose_parser_profile(source), uuid.uuid4(),
                                       1, 1, path.open("rb"))


def make_pdf(path: Path, *, blank_second_page: bool) -> None:
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), "Scope A\nDecision B")
        second = document.new_page()
        if not blank_second_page:
            second.insert_text((72, 72), "Scope C")
        document.save(path)


def verify_native(path: Path) -> None:
    make_pdf(path, blank_second_page=False)
    source, prepared = prepared_file(path)
    try:
        parsed = extract_pdf_text(prepared)
    finally:
        prepared.close()
    assert [node.text for node in parsed.nodes] == ["Scope A", "Decision B", "Scope C"]
    content = parsed.canonical_bytes()
    record_id, document_id = uuid.uuid4(), uuid.uuid4()
    result = VerifiedParseResult(
        record_id, source.document_version_id, uuid.uuid4(),
        parsed.parser_profile, parsed.parser_version, source.content_sha256,
        hashlib.sha256(content).digest(), content,
    )
    proof = ParsedNodeEvidenceProofService(results=ResultPort(result))
    query = DocumentReadQuery(b"s" * 32, uuid.uuid4(), "PROJECT", uuid.uuid4())
    with pymupdf.open(path) as reopened:
        for node in parsed.nodes:
            locator = node.position.to_locator()
            assert locator["locator_type"] == "TEXT_RANGE"
            page_text = reopened[locator["page_no"] - 1].get_text("text", sort=True)
            normalized = unicodedata.normalize(
                "NFC", page_text.replace("\r\n", "\n").replace("\r", "\n"))
            selected = normalized[locator["start_offset"]:locator["end_offset"]]
            assert selected == node.text
            assert hashlib.sha256(selected.encode("utf-8")).hexdigest() == locator["normalized_fingerprint"]
            direct = proof.prove(query, document_id=document_id,
                                 document_version_id=source.document_version_id,
                                 parse_record_id=record_id, locator=locator)
            assert direct.node_id == node.node_id
            assert direct.content_fingerprint == hashlib.sha256(selected.encode("utf-8")).digest()
            structured = {"locator_type": "STRUCTURED_NODE",
                          "parse_record_id": str(record_id), "node_id": node.node_id,
                          "source_locator": locator}
            assert proof.prove(query, document_id=document_id,
                               document_version_id=source.document_version_id,
                               parse_record_id=record_id, locator=structured).node_id == node.node_id
    with path.open("wb") as stream:
        stream.write(b"tampered")
    with path.open("rb") as changed:
        prepared.stream = changed
        try:
            extract_pdf_text(prepared)
        except ParserResultError as error:
            assert error.code == "FILE_INTEGRITY_MISMATCH"
        else:
            raise AssertionError("modified source accepted")


def verify_ocr_boundary(path: Path) -> None:
    make_pdf(path, blank_second_page=True)
    _, prepared = prepared_file(path)
    try:
        try:
            extract_pdf_text(prepared)
        except ParserResultError as error:
            assert error.code == "PARSER_OCR_REQUIRED"
        else:
            raise AssertionError("blank PDF page was accepted as native text")
    finally:
        prepared.close()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="plm-evd-native-pdf-") as scratch:
        root = Path(scratch)
        verify_native(root / "native.pdf")
        verify_ocr_boundary(root / "blank.pdf")
    print("PASS: on-disk native PDF ranges independently reopened and Evidence-proven; "
          "blank page requires OCR and modified bytes fail closed")


if __name__ == "__main__":
    main()
