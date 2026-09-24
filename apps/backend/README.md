# Backend

FastAPI、Worker 与客户运行模块的后端工程根目录。Python 代码使用 `src/plm_assistant` 布局；测试位于 `tests`，不得把本地数据、Secret 或生成物放入源码目录。

## 当前能力

WBS 1.02 已提供无全局单例的 FastAPI app factory：

```powershell
uvicorn --factory plm_assistant.entrypoints.api:create_app
```

当前仅开放 `/health/live` 与 `/health/ready` 最小健康面。Swagger、ReDoc、外部 OpenAPI、数据库、认证、业务 Router 和 Worker 尚未实现；后续 WBS 将分别补齐，不应在 app factory 中提前耦合。

## 开发依赖

项目要求 Python 3.13.x，直接依赖由 `pyproject.toml` 固定。测试按 Starlette 1.7 要求使用 `httpx2`；生产运行不应安装测试依赖组。
