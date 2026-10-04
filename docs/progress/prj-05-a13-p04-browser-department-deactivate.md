# PRJ-05-A13-P04：部门停用 Windows 11 浏览器与隔离数据库验收

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（Windows 11 本机合成端到端，非正式信任或三平台验收）。输入为 P01～P03、后端停用合同和 DEC-20260929-464。
- Changed：自有随机 PostgreSQL/Vault 夹具增加互斥 `--department-deactivate-api-only` 与 `--department-deactivate-browser` 模式。负责人所用 D1 保持 ACTIVE 作为在用拒绝样本，独立无成员 FREE 部门作为可停用目标；无生产程序、API、Schema、Migration、权限或依赖变化。回滚可撤这两种夹具模式。
- HTTP：匿名 401、非负责人/外项目 404、缺 CSRF 403、缺 If-Match 428、在用 D1 409；FREE 首次 200/`"v1"`、原 Key 同请求重放 200、同 Key 版本冲突 409，独立历史读取 INACTIVE/v1。API-only 完整运行 exit0。
- Browser：本机 IAB 用合成账户从项目详情进入部门历史，仅选择无成员的 FREE/ACTIVE/v0，明确勾选后显示首次回执及“不是当前状态证明”；独立刷新后 FREE 显示已停用且不再有停用入口。browser fixture 完整运行 exit0。
- Database/cleanup：两轮均 SQL 核 FREE `INACTIVE/v1`、占用 D1 `ACTIVE/v0`、恰一条 `PROJECT_DEPARTMENT_DEACTIVATED` Audit、不可变结果及完成收据；随机数据库/角色/Vault 清理 exit0。原 PoC PG 开始前停止，结束时亦无进程；尝试正常 stop 时已无进程，日志有 Windows shared-memory reserve 487 但未证实与停机因果，故不把数据库关闭过程标为通过。
- Verification adjustment：首轮 API-only HTTP 已通过，但 SQL 断言错误地以部门 ID 比较收据结果 ID，导致脚本 exit1；按既有数据模型改为通过 `prj_department_deactivate_results.result_id` 关联后，以全新随机资源完整重跑 exit0。错误未修改生产实现。
- Compatibility/upgrade：兼容 DB head `20260927_0049` 与冻结 `/api/v1`；无升级步骤。
- Known Issues/Next：仅合成信任源/Windows 11；正式 TLS/可信时钟、Server 2025/Debian、性能、POC-03 AI 质量、Gate3/可用包未验。本地 PoC PG 偶发非预期退出原因未证实，后续运行前仍需检测并记录状态。
