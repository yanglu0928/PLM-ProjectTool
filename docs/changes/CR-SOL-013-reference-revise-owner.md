# CR-SOL-013：ReferenceSolution 修订版本与当前指针受控写入

日期：2026-10-09；状态：`PLANNED_NOT_IMPLEMENTED`。依据 CR-EXEC-001 持续授权先记录后实施；Gate 2 原冻结提交 `64cdf09` 保留。TraceLink：API-04/DM-05 → CR-SOL-004/005/007、0139～0144 → SOL-01-A04 → SOL-01-A05 → 本 CR。

## 来源、冲突与选择

冻结 `SOL_REFERENCE_REVISE` 要求在 PROJECT PM/实施成员或 GLOBAL DeploymentAdmin 授权下生成新的不可变参考版本，并让后续读取能够定位当前版本。当前 0139 根已有 `current_version_ref`、版本 `supersedes_version_ref` 与有序固定来源表；0144 Guard 只允许 INSERT，根 UPDATE 拒绝，故版本可以插入但无法原子推进当前指针。若仅插入版本，当前读取永远停留旧版；若关闭 Guard 则无关根字段和历史会暴露修改。不能用根当前状态重建原 201 重放，因为它会随下次修订变化。

选择新线性迁移和 Owner 同交付单元最小开放：版本及来源仍仅 INSERT，根只允许受控 `current_version_ref`/`lock_version` 推进，其他身份/资格字段保持不变；根行锁、旧版本/Scope/Project/序号/来源证明和首次结果的不可变恢复由服务端与数据库约束共同保证。幂等重放须返回原新版本快照，不能读取后来的根指针；若现有 Receipt 无法安全固定首次响应，先加独立闭锁快照表。GLOBAL 脱敏确认必须绑定本次新来源指纹，不能沿用旧版本的确认。修订不自动改变 Eligibility，也不生成正式项目 Solution。

## 差异、影响、迁移/回滚与验证

只补冻结 Reference 修订能力，不修改 `/api/v1` 路径、角色、Scope、AI 或正式客户确认规则。与旧 0144 的差异是根的最小列 UPDATE 和可恢复的首次 201；保留所有旧版本/来源及原迁移。实施前细化 ORM、新 Alembic up/down、历史拒降与非空库升级；先在迁移中保持新能力关闭，再由 Owner/Guard 同任务解锁，避免裸露中间态。空库/有历史升级、约束/drift、空历史降级重升、已有修订历史拒降和向前修复路径必须验证。失败时撤下可选路由/关闭 Guard；不得删除已修订版本或强制回滚生产历史。

必测 PROJECT/GLOBAL 权限、同项目/跨项目、当前版本与 supersedes 链、来源当前性和撤回、GLOBAL 脱敏绑定、并发同 Key/不同 Key、原 201 重放、指针/Audit/Receipt 原子回滚、直接 SQL 非法 UPDATE/DELETE/TRUNCATE、License/Session/CSRF、默认应用关闭及 Win11 隔离 PG。HTTP/Windows/UI/浏览器分别独立验收。正式目标账户、Server2025、20 并发和 Release 另验；未取得证据前本 CR 不能标 PASS。
