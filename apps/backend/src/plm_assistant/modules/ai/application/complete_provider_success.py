"""Consume, validate, publish and always close one Provider success response."""

from __future__ import annotations

from .provider_execution_contract import AIProviderResponse
from .provider_response_parser import (
    AIProviderResponseParseError,
    AIProviderSuggestionParser,
)
from .publish_suggestion_success import (
    AITaskSuggestionPublicationError,
    AITaskSuggestionSuccessPublisher,
    PublishedAITaskSuggestion,
)
from .task_invocation_begin import BegunAITaskInvocation
from .task_invocation_prepare import PreparedAITaskInvocation


class AITaskProviderSuccessError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_RESULT_NOT_PUBLISHED") -> None:
        self.code = code
        super().__init__(code)


class AITaskProviderSuccessService:
    def __init__(
        self, *, parser: AIProviderSuggestionParser,
        publisher: AITaskSuggestionSuccessPublisher,
    ) -> None:
        if parser is None or publisher is None:
            raise ValueError("AI Provider success dependencies required")
        self._parser = parser
        self._publisher = publisher

    def complete(
        self, *, prepared: PreparedAITaskInvocation,
        begun: BegunAITaskInvocation, response: AIProviderResponse,
        worker_ref: str,
    ) -> PublishedAITaskSuggestion:
        if type(response) is not AIProviderResponse:
            raise AITaskProviderSuccessError()
        try:
            parsed = self._parser.parse(
                prepared=prepared, begun=begun, response=response,
            )
            return self._publisher.publish(
                parsed=parsed, prepared=prepared, begun=begun,
                worker_ref=worker_ref,
            )
        except AIProviderResponseParseError as error:
            raise AITaskProviderSuccessError(error.code) from None
        except AITaskSuggestionPublicationError as error:
            raise AITaskProviderSuccessError(error.code) from None
        except Exception:
            raise AITaskProviderSuccessError() from None
        finally:
            response.close()
