from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Source:
    file_name: str
    sha256: str
    media_type: str
    size_bytes: int


@dataclass(slots=True)
class Page:
    number: int | None
    label: str
    source_locator: str


@dataclass(slots=True)
class Block:
    id: str
    type: str
    text: str
    page: int | None
    section: str | None
    table: dict[str, Any] | None
    source_locator: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedDocument:
    source: Source
    title: str | None
    pages: list[Page]
    blocks: list[Block]
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    schema_version: str = "poc-05.1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
