# OUTPUT-01-A02：OUT-01 Schema 与固定 Context 持久化

## 状态

`IMPLEMENTED_STATIC_VALIDATION_PASS / DATABASE_ACCEPTANCE_PENDING`

## 本任务范围

- 基线：Gate 2 冻结 `DATA-MODEL-CANDIDATE-V1`、`DB-SCHEMA-CANDIDATE-V1`、`API-CONTRACT-CANDIDATE-V1`。
- 本切片实现 OUT-01 OutputRequest、固定 Context Snapshot、固定来源版本引用、Evidence/Trace 引用的 ORM 与 Alembic revision；不实现 Create Owner、HTTP、Job/Plugin 执行、Artifact 发布/下载或 UI。
- 物理细化按 `docs/changes/CR-OUT-001-output-request-physical-schema.md` 记录；未改变冻结 Root、Project Scope 或 `/api/v1`。

## 实现内容

- 新增 `modules/output/infrastructure/orm.py` 注册四张 OUT-01 表：`out_requests`、`out_context_snapshots`、`out_context_source_refs`、`out_context_evidence_refs`。
- `out_requests` 使用 R-PRJ ProjectId、固定 template version 外键、固定输入 SHA-256、generation、请求状态/幂等/Trace 和运行计数；固定生成唯一索引与 SC-03 live 状态谓词一致。
- Context Snapshot 保存有版本和大小边界的 JSONB、独立 SHA-256 与同 Request/Project 的延迟复合 FK。来源/evidence 子行固定 ordinal、owner/object/version identity，Project/Global scope 受到 CHECK 约束，并通过复合 FK 绑定同一 Context Snapshot。
- Migration `20261026_0220` 追加在 `20261026_0210` 后；Context Snapshot/source/evidence 行用逐表触发器拒绝 UPDATE/DELETE。Downgrade 在离线模式拒绝执行，有数据时拒绝降级。
- Alembic env 注册 Output ORM；metadata inventory 与 migration-head 测试已同步。

## 验证证据

- 定向 schema/migration 测试：5 passed；migration-head + 全 ORM metadata + Output 定向共 12 passed。
- Alembic 从 `20261026_0210` 到 `20261026_0220` 离线 SQL 生成成功，确认四表、约束、索引、复合 FK 与不可变触发器均有 DDL；Alembic history 显示单一 head `20261026_0220`。
- Win11 全后端回归：4194 passed、3 skipped、6224 subtests passed；另有 1 项既有 Windows process inventory 用例因 System32 Windows PowerShell 命令未能执行而失败（`WINDOWS_PROCESS_INVENTORY_UNAVAILABLE`），不触及 Output 代码。前一轮初次运行将 TEMP 指向含中文的项目路径导致 OCR/Prompt 路径测试失败；已改用 ASCII D 盘 Temp 路径完整重跑，相关测试恢复通过。
- Windows backend wheel 构建成功；`py_compile` 通过。未安装 Ruff，因此 Ruff 检查未运行。
- Temp 路径用 `D:\PLMToolTemp\output-01-a02-temp`；未在 C Temp 留下本任务构建输出。

## 未完成/阻塞

- 当前环境未发现 PostgreSQL 18 服务进程、`psql`/`pg_ctl` 客户端或仓库内可复用的 PostgreSQL 二进制。因此尚未执行真实空库升级、有数据升级、在线 downgrade/拒绝有数据降级、重升、Schema introspection/drift、绕 ORM 约束负例，也不能宣称 Migration/DB Schema 验收通过。
- 数据库安装/启动不能由离线 DDL 生成替代；当前没有客户数据或业务写入。
- 下一项仍是 `OUTPUT-01-A02`：连接受控 PostgreSQL 18 测试库，按 CR-OUT-001 完成上述数据库验收，再决定是否关闭该 WBS。期间不开放 Output Create/API。

## 兼容性与回滚

- 对旧应用二进制无 API 行为影响；新 Migration 必须先于未来 Output Owner 部署。
- Downgrade 仅在四表全部为空时允许；若已产生 Request/Context 数据则必须先保留备份并走数据迁移/回滚方案，当前 migration 会失败关闭，不删除业务数据。
- Pilot、Gate 3、正式 Release 结论不变；本实现不使 Output 功能可用或对外发布。
