# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|POC-08：Plugin Host 子进程隔离与独立升级|
|Current Status|POC08_WINDOWS_PASS / DEBIAN_NOT_RUN / PHASE0_BLOCKED_BY_POC03|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04、POC-05 已按批准例外收口；POC-06 Windows 11 全链验收 PASS；POC-08 Windows 11 / Windows Server 2025 全部 PASS；P03-A02~A11、P03-A14、P03-A15 已 PASS|
|Blockers|独立留出集分类准确率 24/50（48.00%）低于 90%，精确引用 37/50（74.00%）低于 98%，P03-A12/P03-A13 与 Phase 0 质量 Gate 保持 FAIL；POC-06 Windows Server 2025 缺少 Microsoft Office；POC-06 与 POC-08 的 Debian 13 尚未验证|
|Pending User Decisions|用户已同意 R10 修复方向并明确不重复本轮真实复验；任何新的客户数据外发、全新留出集真实调用或正式 Gate 仍需按规则单独确认|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-08 Windows 11 与 Windows Server 2025 均为 13/13 测试、10/10 验收场景、20/20 并发调用 PASS；crash/timeout 后 FastAPI 仍健康，敏感环境变量可见数 0；POC-06 Windows 11 PASS，Server Office 缺失|
|Next WBS|POC-08 保持 `IN_PROGRESS`，等待 Debian 13 环境或书面例外；可并行进入不依赖该环境的 POC-09 License 技术验证|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 代决策授权：后续普通业务确认、资料缺口补全、候选项取舍和可回滚方案选择，由 AI 按证据优先、保守默认、最小范围原则直接决定并登记；不再逐项打断用户。该授权不替代正式 Gate、客户数据外发、安全/License、已锁定基线变更、删除 Scope 或不可逆外部操作的专项确认。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-21，周窗口已使用 72%，剩余 28%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-08-plugin-host`
- 最近功能检查点：POC-08 的独立 Python 子进程 + JSON-RPC stdio 路径在 Windows 11 与 Windows Server 2025 通过崩溃、超时、非法 JSON、版本不兼容、完整性篡改、启停、环境隔离、独立升级和 20 并发验证；Debian 13 保持未验证。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
