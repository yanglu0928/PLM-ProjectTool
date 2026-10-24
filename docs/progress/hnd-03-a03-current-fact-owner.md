# HND-03-A03：Handover Workflow 当前事实 Repository/Owner

日期：2026-10-05。结论：`HND_03_A03_CURRENT_FACT_OWNER_INTERNAL_PASS`。下一项：`HND-03-A04` Windows 11 / PostgreSQL 18 真实资格验证。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core，Gate 3保持BLOCKED
当前WBS：HND-03-A03
输入基线：HND-03-A01当前事实边界、A02纯资格合同、冻结DM-02/DM-05和API-02
前置任务：A01/A02 PASS；Document/Evidence/Capability/AI/Review/Trace已有Application Port
涉及模块：handover application/infrastructure，通过其他模块Application Interface重证
涉及实体：HND-01/02/03、DocumentVersion、Evidence、CapabilityVersion/Item、AITask、ReviewRound、TraceLink
涉及API：无公开API变更；本Owner留给后续Workflow写命令在调用方事务内使用
涉及权限：Evidence/Document/Trace Owner使用请求Session重验ProjectManager；无新角色
验收标准：锁定当前正式Handover/Action，重证所有外部当前事实，输出A02最小资格，不commit、不写Workflow
风险：历史Review/Evidence冒充当前、物理文件漂移、Action状态与Event不一致、跨Project Evidence、非阻断Trace扩大Gate
```

## 实施结果

- `SqlAlchemyHandoverWorkflowQualificationRepository` 以共享行锁读当前Analysis、精确`current_approved_version_ref`、Version、Item、当前Version来源Action、响应Document、分目的Evidence及当前State Event；Action行状态与`lock_version` Event不一致时失败关闭。
- `HandoverWorkflowQualificationOwner` 只接受正式ACTIVE/APPROVED/CONFIRMED快照并重算Version fingerprint；通过Document物理Hash读、Evidence固定源、CURRENT_APPROVED Capability、SUCCEEDED GAP_ANALYSIS Task、精确APPROVED ReviewRound和ACTIVE Resolution Trace Owner重证。
- Evidence必须同时落在它的固定上下文：Analysis Item Evidence必须来自Analysis固定文档，Action SUBMISSION/VERIFICATION Evidence必须来自该Action响应DocumentVersion；重用同一Evidence时必须同时满足所有绑定集。
- CLOSED Trace只对保守规则下的阻断Item重证；非阻断GAP/SCOPE的无关CLOSED Action不扩大Gate。但阻断Item的CLOSED仍必须由Trace Owner证明当前ACTIVE且两端有真实Owner。
- Owner无Unit of Work所有权，不初始化、不commit、不产生Audit/收据、不写Checklist；后续Workflow命令必须在自己的授权/License/事务边界内调用。

## 兼容、回滚与验证

模块边界内非破坏增量：无Schema/Migration、公开API、角色、配置、依赖或外发变更。后续停止Workflow注册并移除Owner/Repository可回滚，不改写任何历史。

验证：Owner新增8项，A02+A03定向19项，Review/Action相关31项全部PASS；Windows 11后端全量2733运行/3跳过/0失败；开发wheel SHA-256 `3b5830f9503cc0a8098cb643bf93761146f1d0832e66dcb0514c746976a0b708`。

本项仅为内部实现PASS。真实PostgreSQL 18的行锁、正反例、并发漂移和零写尚未执行，不以单元测试代替；由A04关闭。Gate 3、Workflow Checklist写链和Stage Transition仍未通过。
