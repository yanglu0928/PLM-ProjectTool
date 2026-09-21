# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|Phase 0 阻塞项收口：POC-03 / POC-06|
|Current Status|POC08_POC09_PASS_WITH_EXCEPTION / PHASE0_BLOCKED_BY_POC03_POC06|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04、POC-05、POC-08、POC-09 已按批准例外收口；POC-06 Windows 11 全链验收 PASS；P03-A02~A11、P03-A14、P03-A15 已 PASS|
|Blockers|独立留出集分类准确率 24/50（48.00%）低于 90%，精确引用 37/50（74.00%）低于 98%，P03-A12/P03-A13 与 Phase 0 质量 Gate 保持 FAIL；POC-06 Windows Server 2025 缺少 Microsoft Office|
|Pending User Decisions|用户已同意 R10 修复方向并明确不重复本轮真实复验；任何新的客户数据外发、全新留出集真实调用或正式 Gate 仍需按规则单独确认|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-09 Windows 11 与 Windows Server 2025 均为 26/26 测试、10/10 验收场景 PASS；8/8 非法授权拒绝，核心覆盖率 91%～94%，私钥与原始 MAC 未落盘|
|Next WBS|POC-03 质量 Gate 与 POC-06 Windows Server 2025 Office 均需要独立 L3/环境处理；未解除前不得进入 Architecture Freeze|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 代决策授权：后续普通业务确认、资料缺口补全、候选项取舍和可回滚方案选择，由 AI 按证据优先、保守默认、最小范围原则直接决定并登记；不再逐项打断用户。该授权不替代正式 Gate、客户数据外发、安全/License、已锁定基线变更、删除 Scope 或不可逆外部操作的专项确认。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-21，周窗口已使用 73%，剩余 27%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-09-license`
- 最近功能检查点：用户批准 `EXC-P0-005` 暂缓剩余 Debian 13 验证；POC-08、POC-09 以 `PASS_WITH_EXCEPTION` 收口，POC-06 仍由 Windows Server 2025 Office 缺失阻塞。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
