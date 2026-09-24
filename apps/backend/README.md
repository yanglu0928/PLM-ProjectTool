# Backend

FastAPI、Worker 与客户运行模块的后端工程根目录。Python 代码使用 `src/plm_assistant` 布局；测试位于 `tests`，不得把本地数据、Secret 或生成物放入源码目录。

## 当前能力

WBS 1.02 已提供无全局单例的 FastAPI app factory，WBS 1.04～1.05 增加 PostgreSQL SQLAlchemy Session/UnitOfWork 与正式 Alembic 基础设施：

```powershell
uvicorn --factory plm_assistant.entrypoints.api:create_app
```

当前仅开放 `/health/live` 与 `/health/ready` 最小健康面。数据库驱动固定为 `postgresql+psycopg`；Session 由 `DatabaseRuntime` 按事务创建，不使用全局 Session。UnitOfWork 必须显式 `commit()`，异常或遗漏提交会回滚并关闭 Session。

数据库 URL 只由 Composition Root 或迁移入口注入；本模块不读取 `.env` 或 Secret 文件，也不输出明文密码。正式 ORM Base 固定使用 `plm` Schema；首个 revision `20260924_0001` 只建立 PostgreSQL 18 + pgvector 0.8.6 平台基线，业务表仍为 0。

Migration 文件随 backend wheel 交付。`plm` Schema、`plm.alembic_version` 和共享 pgvector 扩展在 downgrade 到 base 后保留；后续模块只能新增自己的正式 ORM/Migration，不得复制 SC-04 的验证性占位表。当前不注册业务 API；认证、业务 Router、Worker 与 Config/Secret 仍由后续 WBS 实现。

## 开发依赖

项目要求 Python 3.13.x，直接依赖由 `pyproject.toml` 固定。测试按 Starlette 1.7 要求使用 `httpx2`；生产运行不应安装测试依赖组。
