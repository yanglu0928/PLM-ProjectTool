# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 2：Platform Core|
|Current WBS|`LIC-01-A03 受控导入命令与初始安装记录`（已完成）|
|Current Status|PHASE_1_COMPLETE / LIC_01_A03_PASS / PHASE_2_IN_PROGRESS|
|Completed Phases|Phase 0 技术验证（`COMPLETE_WITH_APPROVED_ALTERNATIVES`）；Architecture / Data Model / DB Schema / API Contract Freeze；Gate 2 `APPROVED`；Phase 1 基础工程|
|Completed WBS|POC-01、POC-02、POC-04、POC-05、POC-06、POC-08、POC-09 已按验证或批准例外收口；POC-03 以批准替代方案收口；Gate 1 已通过；AF-01～AF-05、DM-01～DM-06、SC-01～SC-05、API-01～API-05 PASS；Gate 2 已批准并冻结四份基线；1.01～1.09、PLT-01-A01～A03、AUD-01-A01～A03、AUT-01-A01～A03、AUT-02-A01～A05、LIC-01-A01～A03、LIC-02-A01～A03、LIC-03-A01～A02 PASS|
|Blockers|LIC-02-A02 的载荷冲突已由 CR-LIC-001 方案 B 解除；POC-03 质量失败继续阻塞 Gate 3/UAT，Server Office、Debian 未验证和 Ghostscript 发行合规继续作为 Release 约束|
|Pending User Decisions|当前无待决策；任何新的客户数据外发仍需当轮明确授权|
|Architecture Version|`ARCH-CANDIDATE-V1`；Gate 2 原冻结内容 `64cdf09`，License ADR-006 经用户批准 CR-LIC-001 修订|
|Data Model Version|`DATA-MODEL-CANDIDATE-V1`；Gate 2 原冻结内容 `64cdf09`，DM-02 License 授权粒度经用户批准 CR-LIC-001 修订|
|DB Schema Version|`DB-SCHEMA-CANDIDATE-V1`；SC-01～SC-05 PASS，Gate 2 已冻结（内容提交 `64cdf09`）；SC-04 Migration 仅为验证性实现|
|API Contract Version|`API-CONTRACT-CANDIDATE-V1`；API-01～API-05 PASS，Gate 2 已冻结（内容提交 `64cdf09`）|
|Test Summary|LIC-01-A03：Windows 11/Python 3.13 后端 155/155 PASS；PostgreSQL 18.6 临时库 Session/CSRF/Role/撤销权限、导入/拒绝审计事务与回滚 PASS；wheel 构建 PASS；无公开业务 API|
|Next WBS|`LIC-01-A04 受控激活与部署验证状态投影`|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 代决策授权：后续普通业务确认、资料缺口补全、候选项取舍和可回滚方案选择，由 AI 按证据优先、保守默认、最小范围原则直接决定并登记；不再逐项打断用户。该授权不替代正式 Gate、客户数据外发、安全/License、已锁定基线变更、删除 Scope 或不可逆外部操作的专项确认。
- 周额度规则：用户已于 2026-09-23 取消自动检查和 20% 停止线；后续仅在用户明确要求时查询。额度重置或购买仍需逐次明确确认。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`feature/license-controlled-import`
- 最近功能检查点：LIC-01-A03 已实现受控内部导入：当前有效 Session+CSRF+DeploymentAdmin 授权，Ed25519 预检通过后写 IMPORTED 安装与不可变文档，拒绝时只留脱敏验证事实和 Audit；导入后仍需综合验证与受控激活，部署级 ValidationState 未更新。生产公钥及选定 MAC 配置、可信时间密钥来源/初始化仍未接线，不得对外开放 License 业务。Auth 仍无公开登录或管理 API。
- LIC-02-A02 冻结冲突已由用户明确批准方案 B；正式差异见 `docs/changes/CR-LIC-001-single-product-full-bundle.md`。V2.1 原文保留历史，专项补充为当前 License 授权粒度基线。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
