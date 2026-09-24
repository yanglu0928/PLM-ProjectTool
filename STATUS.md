# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 2：Platform Core|
|Current WBS|`LIC-03-A01 TrustedTimeState ORM/Migration`（下一任务）|
|Current Status|PHASE_1_COMPLETE / LIC_02_A01_PASS / PHASE_2_IN_PROGRESS|
|Completed Phases|Phase 0 技术验证（`COMPLETE_WITH_APPROVED_ALTERNATIVES`）；Architecture / Data Model / DB Schema / API Contract Freeze；Gate 2 `APPROVED`；Phase 1 基础工程|
|Completed WBS|POC-01、POC-02、POC-04、POC-05、POC-06、POC-08、POC-09 已按验证或批准例外收口；POC-03 以批准替代方案收口；Gate 1 已通过；AF-01～AF-05、DM-01～DM-06、SC-01～SC-05、API-01～API-05 PASS；Gate 2 已批准并冻结四份基线；1.01～1.09、PLT-01-A01～A03、AUD-01-A01～A03、AUT-01-A01～A03、AUT-02-A01～A05、LIC-01-A01～A02、LIC-02-A01 PASS|
|Blockers|Gate 2 对正式开发的阻塞已解除；POC-03 质量失败继续阻塞 Gate 3/UAT，Server Office、Debian 未验证和 Ghostscript 发行合规继续作为 Release 约束|
|Pending User Decisions|当前无待决策；任何新的客户数据外发仍需当轮明确授权；冻结基线变更须 L3 明确批准|
|Architecture Version|`ARCH-CANDIDATE-V1`；AF-01～AF-05 PASS，Gate 2 已冻结（内容提交 `64cdf09`）|
|Data Model Version|`DATA-MODEL-CANDIDATE-V1`；DM-01～DM-06 PASS，Gate 2 已冻结（内容提交 `64cdf09`）|
|DB Schema Version|`DB-SCHEMA-CANDIDATE-V1`；SC-01～SC-05 PASS，Gate 2 已冻结（内容提交 `64cdf09`）；SC-04 Migration 仅为验证性实现|
|API Contract Version|`API-CONTRACT-CANDIDATE-V1`；API-01～API-05 PASS，Gate 2 已冻结（内容提交 `64cdf09`）|
|Test Summary|LIC-02-A01：Windows 11/Python 3.13 后端 132/132 PASS；PostgreSQL 18.6 空库/已有安装升级、旧脏引用预检、ORM drift=0、约束负例、非空回退拒绝和含验证历史恢复 PASS；无公开业务 API|
|Next WBS|`LIC-03-A01 TrustedTimeState ORM/Migration`|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 代决策授权：后续普通业务确认、资料缺口补全、候选项取舍和可回滚方案选择，由 AI 按证据优先、保守默认、最小范围原则直接决定并登记；不再逐项打断用户。该授权不替代正式 Gate、客户数据外发、安全/License、已锁定基线变更、删除 Scope 或不可逆外部操作的专项确认。
- 周额度规则：用户已于 2026-09-23 取消自动检查和 20% 停止线；后续仅在用户明确要求时查询。额度重置或购买仍需逐次明确确认。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`feature/license-validation-state`
- 最近功能检查点：LIC-02-A01 已建立验证状态与事件存储，但状态行不证明 License 有效；可信时间、机器/产品/功能规则、导入/激活、生产公钥装配与 Audit 均未实现。Auth 仍无公开登录或管理 API；下一项为 TrustedTimeState 持久层。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
