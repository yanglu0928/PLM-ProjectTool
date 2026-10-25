"""Local synthetic text/CSV files: real Parser offsets to Evidence proof."""

from __future__ import annotations

import csv
import hashlib
import tempfile
import uuid
from pathlib import Path

from plm_assistant.modules.document.application.read_documents import DocumentReadQuery
from plm_assistant.modules.document.application.read_parse_result import VerifiedParseResult
from plm_assistant.modules.evidence.application.parsed_node_proof import (
    EvidenceNodeProofError, ParsedNodeEvidenceProofService,
)
from plm_assistant.modules.parser.application.extract_textual import extract_textual
from plm_assistant.modules.parser.application.prepare_input import VerifiedParserInput
from plm_assistant.modules.parser.application.profile_selection import (
    ParserInputVersion, choose_parser_profile,
)
from plm_assistant.modules.parser.application.structured_result import ParserResultError


class ResultPort:
    def __init__(self, result: VerifiedParseResult) -> None:
        self.result = result

    def read(self, *_args, **_kwargs) -> VerifiedParseResult:
        return self.result


def parse_file(path: Path, mime: str):
    raw = path.read_bytes()
    source = ParserInputVersion(uuid.uuid4(), hashlib.sha256(raw).digest(), len(raw), mime)
    with path.open("rb") as stream:
        prepared = VerifiedParserInput(choose_parser_profile(source), uuid.uuid4(), 1, 1, stream)
        parsed = extract_textual(prepared)
    return source, parsed


def prove_all(source: ParserInputVersion, parsed) -> None:
    content = parsed.canonical_bytes()
    record_id = uuid.uuid4()
    fixed = VerifiedParseResult(
        record_id, source.document_version_id, uuid.uuid4(),
        parsed.parser_profile, parsed.parser_version, source.content_sha256,
        hashlib.sha256(content).digest(), content,
    )
    query = DocumentReadQuery(b"s" * 32, uuid.uuid4(), "PROJECT", uuid.uuid4())
    service = ParsedNodeEvidenceProofService(results=ResultPort(fixed))
    for node in parsed.nodes:
        locator = node.position.to_locator()
        if not node.text:
            try:
                service.prove(query, document_id=uuid.uuid4(),
                              document_version_id=source.document_version_id,
                              parse_record_id=record_id, locator=locator)
            except EvidenceNodeProofError:
                continue
            raise AssertionError("empty source node became Evidence")
        proof = service.prove(query, document_id=uuid.uuid4(),
                              document_version_id=source.document_version_id,
                              parse_record_id=record_id, locator=locator)
        assert proof.node_id == node.node_id
        assert proof.content_fingerprint == hashlib.sha256(node.text.encode()).digest()
        structured = {"locator_type": "STRUCTURED_NODE",
                      "parse_record_id": str(record_id), "node_id": node.node_id,
                      "source_locator": locator}
        assert service.prove(query, document_id=uuid.uuid4(),
                             document_version_id=source.document_version_id,
                             parse_record_id=record_id, locator=structured).node_id == node.node_id


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="plm-evd-textual-") as scratch:
        root = Path(scratch)
        text_path = root / "synthetic.txt"
        text_path.write_bytes(b"\xef\xbb\xbf" + "甲\r\n\r乙\n".encode())
        text_source, text_result = parse_file(text_path, "text/plain")
        normalized = "甲\n\n乙\n"
        assert len(text_result.nodes) == 2
        for node in text_result.nodes:
            position = node.position.to_locator()
            selected = normalized[position["start_offset"]:position["end_offset"]]
            assert selected == node.text
            assert position["normalized_fingerprint"] == hashlib.sha256(selected.encode()).hexdigest()
        prove_all(text_source, text_result)

        csv_path = root / "synthetic.csv"
        csv_path.write_bytes("名称,备注\r\n测试,\"多行\n内容\"\r\n,尾列\r\n".encode())
        csv_source, csv_result = parse_file(csv_path, "text/csv")
        with csv_path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.reader(stream, strict=True))
        assert len(csv_result.nodes) == 6
        for node in csv_result.nodes:
            locator = node.position.to_locator()
            cell = locator["start_cell"]
            column = ord(cell[0]) - ord("A")
            row = int(cell[1:]) - 1
            assert rows[row][column] == node.text
        prove_all(csv_source, csv_result)

        csv_path.write_bytes(b"tampered,source")
        with csv_path.open("rb") as stream:
            stale = VerifiedParserInput(choose_parser_profile(csv_source), uuid.uuid4(), 1, 1, stream)
            try:
                extract_textual(stale)
            except ParserResultError as error:
                assert error.code == "FILE_INTEGRITY_MISMATCH"
            else:
                raise AssertionError("changed source accepted")
    print("PASS: real synthetic TXT/CSV files, exact character/A1 locations, "
          "nonempty Evidence nodes, empty-cell rejection and source tamper")


if __name__ == "__main__":
    main()
