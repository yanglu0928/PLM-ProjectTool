# PRJ-05-A12-P04：部门更新 Windows 11 浏览器与隔离数据库验收

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（Windows 11 本机合成端到端，非正式信任或三平台验收）。输入为 P01～P03、后端 PATCH 合同和 DEC-20260929-460。
- Changed：自有随机 PostgreSQL/Vault 夹具增加部门 PATCH API-only 与 browser 验证模式；无生产程序、API、Schema、Migration、权限或依赖变化。回滚可移除这两种夹具模式。
- HTTP：匿名 401、非负责人及跨项目 404、缺 CSRF 403、缺 If-Match 428；负责人从 `"v0"` 真实变更到 `"v1"`，旧版重写 409，无变化 `"v1"` 保持，历史独立读取新值。API-only 完整运行 exit0。
- Browser：本机 IAB 使用合成账户，从项目详情进入部门历史，选择 ACTIVE 部门，把编号改为 `NEW`、名称改为 `Synthetic Patched Department` 并明确勾选；显示 `"v1"` 本次回执而非当前状态，刷新历史后独立读到新值。实际 browser/PG 运行 exit0。
- Database/cleanup：两轮各 SQL 核目标 `NEW / new / Synthetic Patched Department / ACTIVE / v1`，仅一条 `PROJECT_DEPARTMENT_PATCHED` Audit，无 PATCH 幂等收据；两轮随机数据库/角色/Vault 清理。原 PoC PostgreSQL 开始前停止，验收后恢复停止。
- Compatibility/upgrade：兼容 DB head `20260927_0049` 与冻结 `/api/v1`；无升级步骤。
- Known Issues/Next：仅合成信任源与 Windows 11 本机，未证明正式 TLS/可信时钟、Server 2025/Debian、性能、POC-03 AI 质量或 Gate3/可用包。下一任务 `PRJ-05-A13-P01` 部门停用前端固定传输。
