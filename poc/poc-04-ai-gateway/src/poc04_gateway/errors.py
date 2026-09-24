from __future__ import annotations


class AIError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status_code = status_code


def error_for_status(status_code: int) -> AIError:
    if status_code == 401:
        return AIError(
            "AI_AUTH_FAILED",
            "AI provider authentication failed.",
            status_code=status_code,
        )
    if status_code == 429:
        return AIError(
            "AI_RATE_LIMIT",
            "AI provider rate limit reached.",
            retryable=True,
            status_code=status_code,
        )
    if status_code in {500, 503}:
        return AIError(
            "AI_PROVIDER_UNAVAILABLE",
            "AI provider is temporarily unavailable.",
            retryable=True,
            status_code=status_code,
        )
    if status_code in {400, 422}:
        return AIError(
            "AI_REQUEST_INVALID",
            "AI provider rejected the request.",
            status_code=status_code,
        )
    return AIError(
        "AI_PROVIDER_HTTP",
        f"AI provider returned HTTP {status_code}.",
        retryable=status_code >= 500,
        status_code=status_code,
    )
