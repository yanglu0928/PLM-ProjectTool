# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P05-A19：真实扫描 PDF 分层语义准确率收口|
|Current Status|POC05_PASS_WITH_EXCEPTION / PHASE0_BLOCKED_BY_POC03|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04、POC-05 已按批准例外收口；P03-A02~A11、P03-A14、P03-A15 已 PASS；P03-A11 已由 50 条独立留出集 98.00% 再验证 PASS|
|Blockers|独立留出集分类准确率 24/50（48.00%）低于 90%，精确引用 37/50（74.00%）低于 98%；R10 诊断确认能力适配标签缺少跨来源对照输入、Prompt 混合条款存在与能力满足、46/50 引用首位候选，且至少 8 条引用失例存在可接受引用集合潜在漏标。P03-A12/P03-A13 与 Phase 0 质量 Gate 保持 FAIL|
|Pending User Decisions|用户已同意 R10 修复方向并明确不重复本轮真实复验；任何新的客户数据外发、全新留出集真实调用或正式 Gate 仍需按规则单独确认|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 203/203、POC-04 12/12 单元测试 PASS；POC-05 真实扫描分层审计覆盖 5 份文档、15 页、75 个视觉真值检查点，PaddleOCR 75/75、关键错误 0，Tesseract 基线 70/75 并保持 FAIL；语义审计新增 3/3 单元测试 PASS，本轮外部调用 0|
|Next WBS|POC-03 保持历史 FAIL 且不进入冻结；继续处理不依赖该质量结论的 POC-06 Word / PPT 验证|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 代决策授权：后续普通业务确认、资料缺口补全、候选项取舍和可回滚方案选择，由 AI 按证据优先、保守默认、最小范围原则直接决定并登记；不再逐项打断用户。该授权不替代正式 Gate、客户数据外发、安全/License、已锁定基线变更、删除 Scope 或不可逆外部操作的专项确认。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-21，周窗口已使用 70%，剩余 30%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：用户同意 R10 方向后完成 R11 离线实现。Prompt v3 显式区分 `DOCUMENT_ASSERTION` 与 `CAPABILITY_FIT`，能力适配必须同时提供需求证据和标准能力证据；Evidence Selector 比较候选支持度，原始名次只作同分规则。10 项合成测试和 POC-03 全量 203 项测试通过；未读取本轮 50 条调规则，未重复真实复验，未产生外部调用。质量 Gate 和历史分数不变。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
