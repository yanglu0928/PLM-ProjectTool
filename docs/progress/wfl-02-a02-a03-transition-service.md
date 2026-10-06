# WFL-02-A02-A03：Handover 受权 Stage Transition 命令

日期：2026-10-06。结论：`WFL_02_A02_A03_TRANSITION_SERVICE_PG_PASS`。
本项关闭内部受权命令，不代表公开HTTP、Windows生产组合、前端、完整六阶段、Gate 3或发行通过。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：WFL-02-A02-A03
输入基线：冻结API-02/DM-02、DEC-904/905、六阶段定义V1、A02 caller-transaction仓储
前置任务：Handover两项真实Owner、两项当前Checklist PASS、Transition原子追加/回读
涉及模块：workflow application、project authorization；不改handover Owner
涉及实体：ProjectWorkflow、Stage、Checklist Record、Transition/Gate、Audit、IdempotencyReceipt
涉及API：无公开路由；内部Operation注册为WORKFLOW_TRANSITION
涉及权限：有效Session+CSRF、ProjectManager、ACTIVE Project、有效License
验收标准：Owner→Workflow锁序、双Gate同源、原子Audit/receipt、失败回滚、原键精确重放
风险与回滚：只注册HANDOVER→SURVEY，WAIVED及其他阶段关闭；停用Service/Operation可回滚，历史不改写
```

## 实施结果

- 新增`WorkflowStageTransitionService`和write-only Session/CSRF命令，只允许目标`SURVEY`；来源阶段继续由A02仓储从数据库权威状态确定，客户端不能指定或覆盖。
- 沿用先认证、再License、再写事务内重认证的防泄漏顺序；项目Owner新增`WORKFLOW_TRANSITION`策略，仅ACTIVE项目的ProjectManager可执行。
- 新命令先保留持久幂等Scope，再按`HANDOVER_BASELINE`、`HANDOVER_ISSUES`固定顺序调用真实Handover Owner；两项必须属于同一Project、Approved Version、Review、Round、Subject及Subject fingerprint，随后才调用Transition仓储。
- Owner的当前Evidence/Review观测转换为最小typed refs，不复制文档正文、路径或AI内容。发生时间在两项重证后取得，A02继续核对当前PASS Record和全部依据。
- Transition、Workflow/Stage状态、`WORKFLOW_STAGE_TRANSITIONED` Audit及`V1_WORKFLOW_TRANSITION`完成收据在一个UOW提交；原键重放仍重验当前身份、License和项目权限，只读取原Transition，不重跑Owner或写第二条历史。
- 无Schema/Migration、冻结URL/DTO、依赖、配置、Secret、客户数据或外发变化；实现与冻结ProjectManager权限一致，无需Change Request。删除新增Service并撤Operation注册可停止新迁移，已提交历史保留。

## 客观验证

- 定向12项通过：固定Owner顺序、双Gate一致性、Audit/receipt/commit、原结果重放、非经理、License、Audit失败、非法目标/版本/理由、仓储异常安全映射及Project权限矩阵。
- Windows 11/PostgreSQL 18.6真实隔离链使用已批准Handover、真实Document字节、Evidence/Capability/AI/Review/VERIFIED Action、Session/CSRF、ProjectManager、License和两个当前Checklist PASS；Audit故障时Workflow保持HANDOVER/v3且Transition/receipt零残留，恢复后仅一条HANDOVER→SURVEY、两Gate、一Audit、一完成receipt，原键重放无重复。
- Alembic autogenerate无新操作；临时数据库和文件由上游Handover fixture清理。
- 首次全量回归因新增防御检查正确拒绝测试夹具中两项Gate不同的合成Review Subject，修正夹具为同一Review Subject后最终后端`2773`项通过、`3`项既有条件跳过；产品约束未放宽。
- 开发wheel共`1012`项并包含新命令模块；SHA-256：`1d9e65f0bf6515d31aa7581255388d368361ce90f5aeaf30108638736724bdfa`。

## 后续边界

下一项`WFL-02-A02-A04`核定并实现冻结`WORKFLOW_TRANSITION` HTTP传输。冻结请求中的`gate_snapshot_refs`尚无可执行嵌套格式；HTTP不得把客户端refs当Owner证明，也不得猜造Breaking DTO，需先形成兼容投影决策，再独立完成Windows组合、前端和真实浏览器。
