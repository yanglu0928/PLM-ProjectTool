from __future__ import annotations


class PluginHostError(RuntimeError):
    def __init__(self, code: str, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail

    def as_dict(self) -> dict[str, str]:
        result = {"code": self.code, "message": self.message}
        if self.detail:
            result["detail"] = self.detail
        return result
