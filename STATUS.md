# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 2：Platform Core|
|Current WBS|`LIC-03-A02 TrustedTimeStatePort 单调更新与完整性边界`（已完成）|
|Current Status|PHASE_1_COMPLETE / LIC_03_A02_PASS / PHASE_2_IN_PROGRESS|
|Completed Phases|Phase 0 技术验证（`COMPLETE_WITH_APPROVED_ALTERNATIVES`）；Architecture / Data Model / DB Schema / API Contract Freeze；Gate 2 `APPROVED`；Phase 1 基础工程|
|Completed WBS|POC-01、POC-02、POC-04、POC-05、POC-06、POC-08、POC-09 已按验证或批准例外收口；POC-03 以批准替代方案收口；Gate 1 已通过；AF-01～AF-05、DM-01～DM-06、SC-01～SC-05、API-01～API-05 PASS；Gate 2 已批准并冻结四份基线；1.01～1.09、PLT-01-A01～A03、AUD-01-A01～A03、AUT-01-A01～A03、AUT-02-A01～A05、LIC-01-A01～A02、LIC-02-A01、LIC-03-A01～A02 PASS|
|Blockers|Gate 2 对正式开发的阻塞已解除；POC-03 质量失败继续阻塞 Gate 3/UAT，Server Office、Debian 未验证和 Ghostscript 发行合规继续作为 Release 约束|
|Pending User Decisions|当前无待决策；任何新的客户数据外发仍需当轮明确授权；冻结基线变更须 L3 明确批准|
|Architecture Version|`ARCH-CANDIDATE-V1`；AF-01～AF-05 PASS，Gate 2 已冻结（内容提交 `64cdf09`）|
|Data Model Version|`DATA-MODEL-CANDIDATE-V1`；DM-01～DM-06 PASS，Gate 2 已冻结（内容提交 `64cdf09`）|
|DB Schema Version|`DB-SCHEMA-CANDIDATE-V1`；SC-01～SC-05 PASS，Gate 2 已冻结（内容提交 `64cdf09`）；SC-04 Migration 仅为验证性实现|
|API Contract Version|`API-CONTRACT-CANDIDATE-V1`；API-01～API-05 PASS，Gate 2 已冻结（内容提交 `64cdf09`）|
|Test Summary|LIC-03-A02：Windows 11/Python 3.13 后端 139/139 PASS；可信时间组件覆盖率 97%；PostgreSQL 18.6 并发/回拨/篡改拒绝及持久审计 PASS；无公开业务 API|
|Next WBS|`LIC-02-A02 LicenseService 签名/Schema/产品/功能/机器/时间综合验证`（先定义正式 Payload 语义并保持冻结信任边界）|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 代决策授权：后续普通业务确认、资料缺口补全、候选项取舍和可回滚方案选择，由 AI 按证据优先、保守默认、最小范围原则直接决定并登记；不再逐项打断用户。该授权不替代正式 Gate、客户数据外发、安全/License、已锁定基线变更、删除 Scope 或不可逆外部操作的专项确认。
- 周额度规则：用户已于 2026-09-23 取消自动检查和 20% 停止线；后续仅在用户明确要求时查询。额度重置或购买仍需逐次明确确认。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`feature/license-trusted-time-port`
- 最近功能检查点：LIC-03-A02 已实现内部 TrustedTimeStatePort、注入式 HMAC 完整性、预期版本原子前移、失败关闭与同/独立事务 Audit。生产密钥来源及一次性初态装配未接线；高权限数据库初态重置或数据库与密钥同时回滚不可由本方案检测。机器/产品/功能综合验证、导入/激活、生产公钥装配仍未实现，不能据此开放 License 业务。Auth 仍无公开登录或管理 API。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
