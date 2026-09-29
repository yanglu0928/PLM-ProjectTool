# PRJ-05-A09-P04：Windows 11 成员三状态浏览器与数据库验证

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（Windows 11 本机隔离合成信任源，非正式发行验收）。输入为冻结三状态 API、PRJ-05-A09-P01～P03 与 DEC-20260929-449。
- Changed：扩展自有浏览器 fixture 的 `--member-state-api-only` 和 `--member-state-browser` 独立模式，使用随机 PostgreSQL 库/角色、临时 Vault 测试凭据、合成负责人和目标成员。不改生产程序、API、权限、Schema/Migration 或依赖。
- HTTP/PG：独立模式 exit 0；匿名 401、非负责人 404、无 CSRF 403、跨项目 404、暂停原 Key 重放首次 `"v1"`、同 Key 异输入 409、恢复 `"v2"`、移除 `"v3"`，成员历史仍显示已移除。SQL 核对最终 REMOVED/v3、三条状态 Audit、三份完成收据。
- 浏览器/PG：合成负责人真实登录后在项目成员历史页，对合成目标依次明确确认暂停、恢复、移除。每次页面分别展示首次回执及重新读取的当前历史；移除后历史仍可见、无直接恢复操作。fixture exit 0，SQL 再核 REMOVED/v3、三条 Audit、三份收据，随机库/角色/Vault 与自有服务清理 PASS；PoC PostgreSQL 恢复原停止状态。
- 兼容/升级/回滚：兼容 DB head `20260927_0049`、冻结 `/api/v1`；无程序升级或数据迁移。回滚撤本 fixture 模式即可，前端 P01～P03 与后端保持不变。
- Known Issues/Next：合成 Guard/密钥不等于正式信任锚；Server 2025/Debian、HTTPS、CR-AUT-008 性能、POC-03 质量、Gate 3/UAT/可用发行包仍待。下一 WBS 按功能计划推进部门管理前端前置核查。
