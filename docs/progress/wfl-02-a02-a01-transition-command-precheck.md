# WFL-02-A02-A01：Handover Stage Transition受权命令前置核查

日期：2026-10-06。结论：`WFL_02_A02_A01_TRANSITION_COMMAND_PRECHECK_PASS`。
本项只关闭运行时实施边界，不代表Stage Transition、Gate 3或完整项目流程通过。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：WFL-02-A02-A01
输入基线：冻结DM-02/SC-01/API-02、六阶段定义V1、CR-WFL-003/004、Schema0031/0033
前置任务：Workflow START、Checklist不可变记录/当前查询、Handover两项Owner及真实Edge写闭环
涉及模块：workflow application/infrastructure；handover仅通过既有Application Port
涉及实体：ProjectWorkflow、Stage、ChecklistItem/Record、StageTransition、GateItem/GateRef
涉及API：后续WORKFLOW_TRANSITION；本项不挂载HTTP或修改冻结DTO
涉及权限：后续ProjectManager、ACTIVE Project、Session/CSRF、License、强If-Match、幂等、Audit
验收标准：明确可推进事实、锁序、原子写、重放、失败关闭、回滚及后续WBS拆分
风险与回滚：不把历史PASS/APPROVED或请求UUID当当前证明；本项纯文档可停止后续实现
```

## 当前证据与结论

- 0031已物理化追加式Transition/Gate/typed refs，提交时要求来源Stage完成、目标Stage
  ACTIVE、Workflow指针/版本原子匹配；0033又强制每个GateItem关联一个**已提交且当前**的
  Checklist Record，并要求Gate refs与该Record refs精确同集且观测不回退。
- `SqlAlchemyCurrentChecklistRecordRepository`可在调用方事务内锁定Workflow和Item、重建完整
  Record链并复算摘要；它明确只给历史当前投影，不等于当前Owner批准。
- Handover两项均已有真实资格Owner。其输出可重新证明当前APPROVED Handover Version/Review、
  固定Document/Evidence/Capability/AI及阻断Action，因此Handover→Survey具备唯一的首批运行时
  Gate策略。其他十项Checklist和ApprovedException仍未具备，不得由此类推。
- A10只记录了`HANDOVER_ISSUES` PASS；真实推进还必须在同一项目里另有当前
  `HANDOVER_BASELINE` PASS。单个PASS或历史APPROVED不能推进。
- 冻结`StageTransitionRequest`只概述`target_stage_key/reason/gate_snapshot_refs`，没有给出
  refs的可执行嵌套字段。内部仓储/命令可以先完成；公开HTTP前必须单独固定兼容性请求投影，
  不能自行猜造客户端可控Owner观测。

## 首批受权边界

1. 仅注册`HANDOVER -> SURVEY`；from始终来自数据库当前Workflow，target必须为下一阶段。
2. 先在调用方事务内按固定Item顺序调用Handover Owner重证两项资格，再锁Workflow、来源/目标
   Stage、两项Checklist和当前Record。这样与现有Checklist写链的“业务Owner→Workflow”锁序
   一致，避免反序死锁。
3. 两项当前Record必须为PASS、属于同一Workflow/Project/HANDOVER，且Record refs身份/Scope/
   内容摘要与本次Owner输出精确一致；Gate使用本次更晚或相同的观测版本/时间，不复制正文。
4. 一次事务插入Transition、两个GateItem、全部GateRef，更新HANDOVER为COMPLETED、SURVEY为
   ACTIVE、Workflow当前阶段及lock version +1，并由外层命令追加Audit和完成幂等收据。
5. 任一授权、许可、版本、Owner、Record链、依据或数据库完整性失败，均不得留下成功历史或
   半套状态。原Key重放只能返回原不可变Transition结果，不能生成第二次推进。
6. WAIVED继续失败关闭：仓库结构已能保存，但当前没有ApprovedException实体/权限/撤销Owner。

## 任务拆分、兼容与下一项

- `WFL-02-A02-A02`：只实现caller-transaction Transition追加仓储及读取原结果，验证完整
  原子状态/历史/回滚/并发；不含Session、License、Audit、收据或HTTP。
- `WFL-02-A02-A03`：实现仅Handover策略的受权命令、Owner重证、Audit/持久幂等。
- 后续独立完成严格HTTP、Windows真实PG组合、前端与浏览器；`gate_snapshot_refs`如需精确
  增量合同，先登记API Change Request并保持冻结字段兼容。
- 本项无代码、Schema/Migration、API、权限、依赖、Secret、网络或客户数据外发变化。
  0031/0033及原冻结提交保留；停止后续实现即可回滚本计划。
