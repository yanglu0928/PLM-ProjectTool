"""Fail-closed, dedicated Windows key source for Document upload tokens."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


DOCUMENT_UPLOAD_TOKEN_KEY_REF = "document-upload-token-v1"


class UploadTokenKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionUploadTokenStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("document upload token key unavailable")


def create_windows_document_upload_token_issuer(
    *, resolver: UploadTokenKeyResolverPort | None = None,
) -> HmacUploadTokenIssuer:
    source = resolver or WindowsSecretKeyProvider()
    try:
        key = source.resolve_key(DOCUMENT_UPLOAD_TOKEN_KEY_REF)
        if type(key) is not bytes or len(key) != 32:
            raise ProductionUploadTokenStartupError()
        return HmacUploadTokenIssuer(provider=source, key_ref=DOCUMENT_UPLOAD_TOKEN_KEY_REF)
    except Exception:
        raise ProductionUploadTokenStartupError() from None
