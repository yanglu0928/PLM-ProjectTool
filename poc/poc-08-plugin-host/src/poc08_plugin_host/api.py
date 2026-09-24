from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .errors import PluginHostError
from .registry import PluginService


class InvokeRequest(BaseModel):
    plugin_id: str = Field(min_length=1)
    method: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=2.0, gt=0, le=30)


def create_app(service: PluginService) -> FastAPI:
    app = FastAPI(title="POC-08 Plugin Host", version="0.1")

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"data": {"status": "ok"}, "trace_id": str(uuid4())}

    @app.post("/poc/plugin/invoke")
    def invoke(payload: InvokeRequest):
        trace_id = str(uuid4())
        try:
            result = service.invoke(
                payload.plugin_id,
                payload.method,
                payload.params,
                timeout_seconds=payload.timeout_seconds,
            )
            return {
                "data": {
                    "result": result.result,
                    "plugin_id": result.plugin_id,
                    "plugin_version": result.plugin_version,
                },
                "trace_id": trace_id,
            }
        except PluginHostError as exc:
            status_code = 504 if exc.code == "PLUGIN_TIMEOUT" else 502
            return JSONResponse(
                status_code=status_code,
                content={"error": exc.as_dict(), "trace_id": trace_id},
            )

    return app
