# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A11~A13-R8：独立留出集真实质量复验|
|Current Status|PARTIAL_COMPLETE / WAITING_EXPLICIT_BAILIAN_DATA_EGRESS_AUTHORIZATION|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A11、P03-A12-R7、P03-A14、P03-A15 已 PASS|
|Blockers|独立留出集 50/50 已严格导入，Schema 与覆盖审计 PASS；DeepSeek 外发已有明确授权，但安全审查要求另外明确允许将 50 条留出集查询及候选正文发送至百炼 Embedding 与 Reranker。该授权未形成前，真实复验不得执行|
|Pending User Decisions|明确授权或拒绝将本轮 50 条独立留出集的查询及最小必要候选正文发送至阿里云百炼 Embedding 与 Reranker；未获授权前百炼/DeepSeek 均不执行本轮真实复验|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 188/188、POC-04 12/12 单元测试 PASS；留出集 50 条入口与普通 100~200 条校准集限制均失败关闭；组合语料 2,078 个 Chunk、预期证据缺失 0，本机 PostgreSQL 18.6/pgvector 0.8.6 前置检查 PASS；实施 WBS R7 为 5 项目/60 任务/40 证据链接，5/5 页签视觉与公式错误扫描 PASS；管理层汇报 R8.1 为 8 页并通过最终化、逐页渲染与可编辑图表检查；本轮外部调用 0|
|Next WBS|取得百炼 Embedding/Reranker 明确数据外发授权后，执行 50 条独立留出集真实复验并据实更新管理汇报质量页；未授权则保持当前安全检查点|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 代决策授权：后续普通业务确认、资料缺口补全、候选项取舍和可回滚方案选择，由 AI 按证据优先、保守默认、最小范围原则直接决定并登记；不再逐项打断用户。该授权不替代正式 Gate、客户数据外发、安全/License、已锁定基线变更、删除 Scope 或不可逆外部操作的专项确认。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-21，周窗口已使用 66%，剩余 34%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：已生成实施 WBS 草案 R7（5 个项目、60 项任务，其中 40 项需求交付、20 项项目控制）和管理层汇报 R8.1（8 页）。WBS 刻意不填写实名、日期或承诺工期，全部保持 `NOT_FORMAL_WBS`；汇报如实展示校准集 95.00%/42.50%/51.67% 与总体 FAIL，并将独立留出集标记为待百炼外发授权。留出集验证器已允许 `poc-03.holdout.v1` 恰好 50 条，同时保持普通数据集 100~200 条限制；组合语料前置检查通过，外部调用在安全审查前为 0。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
