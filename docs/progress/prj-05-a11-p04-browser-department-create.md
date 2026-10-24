# PRJ-05-A11-P04：部门创建 Windows 11 浏览器与隔离数据库验收

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（Windows 11 本机合成端到端，非正式信任或三平台验收）。输入为 P01～P03、后端创建合同及 DEC-20260929-456。
- Changed：自有随机 PostgreSQL/Vault 夹具增加部门创建 API-only 与 browser 验证模式；无生产程序、API、Schema、Migration、权限或依赖变化。回滚可移除这两种夹具模式。
- HTTP：匿名 401、非负责人及跨项目 404、缺 CSRF 403；负责人 201、原 Key 同载荷重放 201 与 `"v0"`、原 Key 异载荷 409；历史中仅一条新编号。API-only 完整运行 exit0。
- Browser：本机 IAB 使用合成账户登录，从部门历史进入创建页，输入 `NEW` / `Synthetic Created Department` 并勾选明确确认；页面仅显示 `"v0"` 首次回执及非当前状态提示，返回历史独立重读到新部门。实际 browser/PG 运行 exit0。
- Database/cleanup：SQL 核对两轮各仅一条新 `ACTIVE/v0` 部门、该部门单条创建 Audit、单条 `COMPLETED` 幂等收据；两轮随机数据库/角色/Vault 均清理。原 PoC PostgreSQL 开始前停止，验收后恢复停止。
- Compatibility/upgrade：兼容 DB head `20260927_0049` 与冻结 `/api/v1`；无升级步骤。
- Known Issues/Next：仅合成信任源和 Windows 11 本机，未证明正式部署的 TLS、可信时钟、Server 2025/Debian、性能、POC-03 AI 质量或 Gate 3/可用包。下一任务 `PRJ-05-A12-P01` 部门更新前端固定传输；未知创建结果离页后须核历史/审计，不自动新建 Key。
