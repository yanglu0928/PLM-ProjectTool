# SOL-05-A04-P12-P03：适配依据闭锁 Schema 编码前检查

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`WINDOWS_SCHEMA_PASS`；新适配依据仍不可由业务写入。

|检查项|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `SOL-05-A04-P12-P03`，仅增加固定 SpecRef 的可空适配依据持久结构，默认闭锁写入|
|输入基线|Gate 2 DM-05/SC-01/API-04、CR-SOL-022/023、DEC-1205/1206、0180 封印子集合|
|前置任务|P12-P02 方案和迁移/回滚计划已登记并同步；0180 Win11/PG/HTTP 与全量回归已验|
|涉及模块/实体|Solution 的 `sol_section_spec_refs` 与对应 ORM，仅该 owned collection|
|涉及API/权限|本片无 API、权限、License 或前端变化；旧输入/旧201与现有 `spec=UNAVAILABLE` 保持|
|验收标准|0181 nullable `fit_rationale`，旧行 NULL；非空长度/修剪约束；子 Guard 禁止新值写入；空/有数据升级、空新依据降级重升、非空拒降、ORM drift、历史功能回归|
|风险|无界正文、旧引用误补填、绕过 0180 同事务封印、离线 SQL 合同退化或降级丢失已有作者依据|

迁移应在 0180 后追加，不能修改既有迁移。后续 P12-P04 才开放规范化输入及同事务写 Owner；P12-P05 另接现时 VALIDATE。此片即使 Schema 成功，也不得宣称 `spec=PASS` 或客户确认。

## 实施与验收

- 新增 0181/ORM nullable `fit_rationale`，数据库只允许 NULL 或 1～1000 字符且修剪后的文本；现有固定引用保持 NULL，不回填。0180 同事务子集合封印保持，0181 Guard 额外拒绝非 NULL 新值，UPDATE/DELETE/TRUNCATE 仍拒绝。
- Win11/一次性 PG18.6 空库 `0181→0180→0181` 与 head ORM drift 通过；真实 SOL-06 批准并写入的既存 Section 固定引用在 `0180→0181` 升级及空新依据降级重升后仍为 NULL，旧 HTTP/收据/Audit 可用。数据库拒新依据写入、空白/超长值；合成未来非 NULL 历史时拒绝降级，测试只在可弃库中构造并不修改生产数据。
- 后端完整回归 `3901 passed, 3 skipped, 6061 subtests passed`；迁移合同定向 4 项通过，离线升级 SQL 安全合同保持。本片无 API/权限/前端变动，旧输入和 `spec=UNAVAILABLE` 保持。

兼容与回滚：无新增依据历史时可降回 0180 再升级；存在非 NULL 历史拒降，应关闭新增入口并前滚修复，不得删史。下一项 P12-P04-P01 定义可选引用级输入/读取与指纹兼容，P12-P04-P02 才开放受权同事务写 Owner；现时 Spec 维验证及客户 Review 均后续独立验收。
