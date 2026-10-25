# SUR-02-A02：Survey Round 双表 ORM / Migration 0107

日期：2026-10-06。结论：`SUR_02_A02_ROUND_SCHEMA_PASS`。下一项：`SUR-02-A03` PROJECT_RECORD 固定来源证明与 Round source append Port。

## 实现

- 新增 PROJECT/M-PRJ `srv_rounds`：固定 Survey/Version/Project、服务端 Round 序号、计划起止、地点说明、四态生命周期、actor/time、关闭报告指纹和强 `lock_version`。
- 新增 `srv_round_source_records`：只在 OPEN Round 追加固定 PROJECT_RECORD Evidence、Document/Version、可空固定 Question、观测 Evidence 版本/指纹、记录人和序号；禁止更新、删除和截断。
- Migration `20261006_0107` 在创建与 OPEN 时重验当前 ACTIVE Survey 的当前 APPROVED Version；数据库仅允许 `PLANNED -> OPEN -> CLOSED` 或 `PLANNED -> CANCELLED`，有历史时拒绝降级，离线降级失败关闭。
- Schema 层保留合法 CLOSED 状态；应用层 CLOSE 仍按 CR-SUR-007 失败关闭，直至 SUR-03 提供真实 Assignment/Response 完整性 Owner。

## 验证

- Windows 11 / PostgreSQL 18.6：非空 `0106 -> head`、空表 downgrade/re-upgrade、Alembic drift、当前批准版本边界、错误跳态、计划更新、OPEN、PROJECT_RECORD 追加、重复/模板/更新/删除/关闭后追加拒绝、CLOSED 及保留历史拒降全部通过。
- 新 Schema 单元 4 项/18 子断言；后端全量 `2859 passed / 3 skipped`、`4071` 子断言，两个既有依赖弃用 warning 保留。
- 开发 wheel 共 `1061` 项并包含 ORM/0107；SHA-256 `162786f098335bb5dd2b2570d5d9c37651aba48f01a0bff88f9a2757c6d30aee`。该 wheel 仅为开发验证产物，不是可交付安装包。

## 兼容、升级与回滚

0107 只新增冻结 SRV-03 已定义的两张表，不修改既有 Survey 定义表、`/api/v1` JSON、角色、依赖、Secret、网络或外发。空表可降至0106；存在 Round/source 历史时不得物理回滚，应停止后续 Owner 装配并向前修复。Windows Server 2025 留发行矩阵复验，Debian 13 按用户指令跳过实机但仍为正式兼容目标。
