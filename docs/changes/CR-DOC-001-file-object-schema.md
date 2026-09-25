# CR-DOC-001：FileObject 正式持久层增量

日期：2026-09-25；状态：依据 CR-EXEC-001 持续授权实施，DOC-03-A01 已验证；范围：Phase 2 / DOC-03-A01。

## 来源、冲突与证据

Gate 2 冻结 DM-03、SC-01/02 和 API-02 要求 `DOC-03 FileObject` 将受控本地文件与 PostgreSQL 元数据分离，保留 STAGED/AVAILABLE/FAILED/CLEANUP_PENDING/REMOVED/RESTRICTED 状态及状态事件。当前正式 Migration 至 `20260925_0019`，仅有 Project 等表，`doc_file_objects` 和 `doc_file_state_events` 尚不存在。设计基线已冻结，但生产 DDL 未实现；需可追溯的后续 Schema 增量，不回写原冻结提交。

## 方案比较与选择

- 不选把正文放入数据库 bytea 或静态文件目录：违背本地文件系统与元数据化管理及授权边界。
- 不选直接建设上传 HTTP：缺受控 FileObject 状态、恢复事件、DocumentVersion/Job 前置，容易暴露半完成文件。
- 选择先建立 FileObject Root 及仅追加状态事件表，保留 GLOBAL/PROJECT 显式 Scope、Project FK、相对 Locator、Hash/Size/MIME、乐观锁、actor/time 和 Retention 字段；文件字节、上传协议、DocumentVersion 与恢复器分别后续实现。

## 差异、风险、迁移与回滚

新增 ORM/Alembic Migration `20260925_0020`，不修改冻结 `/api/v1`、技术栈或业务规则。目标库升级前备份；空表允许降级至 `0019`，已有 FileObject/状态事件时拒绝普通降级，避免丢失文件归属与恢复证据。数据库 CHECK 只能约束字段形状与相对 Locator 的基础语法；符号链接、重解析点、同卷原子提升、文件 Hash 与跨资源一致性必须由后续 Storage Adapter/恢复器验证，不把本增量标为文件可用。

## 验证计划与剩余风险

验证 ORM/Migration 无差异、空库 up/down、有数据升级、Scope/Project 约束、Hash 长度、状态/大小/Locator 形状、FK 保护、状态事件不可改写及非空降级拒绝。仅在 Windows 11/Python 3.13、PostgreSQL 18 临时库验证；不使用客户文件。Server 2025、Debian 13、真实文件系统崩溃恢复与正式信任源后续另行验收。

验证结果：Windows 11 后端 441/441 PASS；PostgreSQL 18 临时库 Migration/ORM、约束、历史及降级保护 PASS；开发 wheel PASS。FileObject 的实际文件写入/恢复仍未验证，不能标记 Document 模块可用。
