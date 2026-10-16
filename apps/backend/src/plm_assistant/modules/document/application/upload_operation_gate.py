"""Upload operation fence contract spanning short transactions and physical I/O."""

from __future__ import annotations

import uuid
from contextlib import AbstractContextManager
from typing import Protocol


class UploadGateUnavailable(RuntimeError):
    """No exclusive same-upload I/O window could be established."""


class UploadOperationGatePort(Protocol):
    def hold(self, upload_id: uuid.UUID) -> AbstractContextManager[None]: ...
