# SOL-01-A02：Solution Outline/Section 身份持久层

日期：2026-10-08。结果：`SCHEMA_PASS`，仅冻结 SOL-02/SOL-04 的数据库/ORM 基础；真实写 Owner、版本、API 与阶段资格仍待。

```text
当前 Phase：Phase 2 依 CR-SEQ-001 前置 Solution 最小真实 Owner
当前 WBS：SOL-01-A02
输入基线：V2.1 §6.10/Phase 8；冻结 DM-05、SC-01/02、API-04；CR-SOL-001
前置任务：SOL-01-A01 PRECHECK_PASS；Project/User/Alembic 基础已存在
涉及模块：solution（仅 ORM/迁移）；platform migration 注册与仓储清单测试
涉及实体：SolutionOutline、SolutionSection；Project/User 仅外键引用
涉及 API：无，冻结 SOL_* 操作未装配
涉及权限：无公开写权限；Owner 未安装时数据库拒绝所有 DML
验收标准：ORM/迁移同构、项目 FK、同 Outline key 唯一、空/有数据升降级、历史拒降、全量回归
风险：草案身份误作正式方案、批准指针无版本 FK、后续写服务绕过 Review
```

实施：新增两张项目范围逻辑身份表、闭锁触发器、ORM 和 Alembic 注册；维护迁移 HEAD/元数据清单测试。完整列、约束和回滚见 `docs/database-schema/solution-identity-foundation-0136-increment.md`。先记录 CR-SOL-001；此处没有更改冻结 `/api/v1` 或正式业务规则。

验证：首次定向单元 2 PASS；固定端口测试库未运行而超时，不记 PASS，改用一次性隔离 PostgreSQL 18.6 后完成空/既有数据升级、降级重升、三次 drift check、未装配 Owner、跨项目 FK、重复 key、畸形 key、TRUNCATE 与历史拒降。首次全量因两处清单/HEAD 维护断言失败，修复并重跑 `3261 passed, 3 skipped, 4815 subtests passed`。隔离实例停止并清理。开发 wheel 尝试因测试 venv 无 pip、系统 Python 无 setuptools.build_meta 未完成；本项不宣称打包验证。无真实 HTTP、人工 Review、目标 Server2025 或性能验收。

TraceLink：CR-SEQ-001 → SOL-01-A01/DEC-1096 → CR-SOL-001 → Migration 0136/测试 → SOL-01-A02/DEC-1097 → SOL-01-A03。
