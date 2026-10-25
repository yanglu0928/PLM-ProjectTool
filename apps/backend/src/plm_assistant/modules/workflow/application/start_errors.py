"""Stable application-facing failure for atomic Workflow start writes."""


class WorkflowStartRepositoryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
