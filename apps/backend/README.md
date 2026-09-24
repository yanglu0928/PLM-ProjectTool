# Backend

FastAPI、Worker 与客户运行模块的后端工程根目录。Python 代码使用 `src/plm_assistant` 布局；测试位于 `tests`，不得把本地数据、Secret 或生成物放入源码目录。

## 当前能力

WBS 1.02 已提供无全局单例的 FastAPI app factory，WBS 1.04 增加 PostgreSQL SQLAlchemy Session/UnitOfWork 基础设施：

```powershell
uvicorn --factory plm_assistant.entrypoints.api:create_app
```

当前仅开放 `/health/live` 与 `/health/ready` 最小健康面。数据库驱动固定为 `postgresql+psycopg`；Session 由 `DatabaseRuntime` 按事务创建，不使用全局 Session。UnitOfWork 必须显式 `commit()`，异常或遗漏提交会回滚并关闭 Session。

数据库 URL 只由 Composition Root 注入；本模块不读取 `.env` 或 Secret 文件，也不输出明文密码。当前不创建业务 ORM 表或 Migration，不注册业务 API；认证、业务 Router、Worker、Config/Secret 和 Migration 仍由后续 WBS 分别实现。

## 开发依赖

项目要求 Python 3.13.x，直接依赖由 `pyproject.toml` 固定。测试按 Starlette 1.7 要求使用 `httpx2`；生产运行不应安装测试依赖组。
