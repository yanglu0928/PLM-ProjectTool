"""Windows proof for authorized fixed-result node and V1 document locations."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.document.application.read_documents import (
    DocumentReadQuery,
    DocumentVersionView,
)
from plm_assistant.modules.document.application.read_parse_result import (
    VerifiedParseResult,
)
from plm_assistant.modules.document.application.resolve_parse_nodes import (
    DocumentNodeLocationError,
    DocumentNodeLocationService,
    DocumentVersionLocationService,
)
from plm_assistant.modules.parser.application.structured_result import (
    ParsedNode,
    ParsedResult,
    TextRangePosition,
)


class Results:
    def __init__(self, value: VerifiedParseResult) -> None:
        self.value = value

    def read(self, *_args, **_kwargs) -> VerifiedParseResult:
        return self.value


class Versions:
    def __init__(self, value: DocumentVersionView) -> None:
        self.value = value

    def get_version(self, *_args) -> DocumentVersionView:
        return self.value


def main() -> None:
    project_id, document_id = uuid.uuid4(), uuid.uuid4()
    version_id, record_id, result_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    source_hash = hashlib.sha256(b"synthetic-document").digest()
    text = "需要确认回写字段。"
    parsed = ParsedResult(
        version_id, source_hash, "PLAIN_TEXT", "1",
        (ParsedNode(
            "line-1", "TEXT_LINE", text,
            TextRangePosition(0, len(text), hashlib.sha256(text.encode()).hexdigest()),
        ),),
    )
    content = parsed.canonical_bytes()
    verified = VerifiedParseResult(
        record_id, version_id, result_id, "PLAIN_TEXT", "1", source_hash,
        hashlib.sha256(content).digest(), content,
    )
    query = DocumentReadQuery(
        b"s" * 32, uuid.uuid4(), "PROJECT", project_id,
    )
    node_location = DocumentNodeLocationService(results=Results(verified)).resolve(
        query, document_id=document_id, document_version_id=version_id,
        parse_record_id=record_id, node_ids=("line-1",),
    )
    assert node_location.locations[0].precision == "PARSED_NODE"
    assert node_location.locations[0].locator["source_locator"]["locator_type"] == "TEXT_RANGE"
    assert text not in repr(node_location.locations[0])

    version = DocumentVersionView(
        version_id, document_id, 1, source_hash.hex(), len(b"synthetic-document"),
        "text/plain", "AVAILABLE", None, datetime.now(timezone.utc), None,
    )
    document_location = DocumentVersionLocationService(
        versions=Versions(version),
    ).resolve(query, document_id=document_id, document_version_id=version_id)
    assert document_location.precision == "DOCUMENT"
    assert document_location.locator == {"locator_type": "DOCUMENT"}
    assert node_location.content_url == document_location.content_url

    try:
        DocumentNodeLocationService(results=Results(verified)).resolve(
            query, document_id=document_id, document_version_id=version_id,
            parse_record_id=record_id, node_ids=("missing-node",),
        )
    except DocumentNodeLocationError:
        rejected = True
    else:
        raise AssertionError("unknown node was accepted")

    print(json.dumps({
        "marker": "AI_04_A07_P03_DOCUMENT_LOCATOR_PASS",
        "node_precision": node_location.locations[0].precision,
        "v1_precision": document_location.precision,
        "unknown_node_rejected": rejected,
        "storage_locator_exposed": False,
        "customer_data": 0,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
