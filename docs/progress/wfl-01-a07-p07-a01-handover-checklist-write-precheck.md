# WFL-01-A07-P07-A01：Handover Checklist 受权写前置核查

日期：2026-10-05。结论：`WFL_01_A07_P07_A01_HANDOVER_CHECKLIST_WRITE_PRECHECK_PASS`。本项只冻结实现边界，不开放写接口。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core，Gate 3保持BLOCKED
当前WBS：WFL-01-A07-P07-A01
输入基线：冻结API-02、六阶段Workflow V1、CR-WFL-003/004/005、DEC-890～893、HND-03-A02～A04
前置：Workflow 0030/0032当前投影与不可变记录Schema、当前记录查询、真实Handover资格Owner均已验证
涉及模块：workflow、handover、project、auth、license、audit、platform idempotency
涉及实体：ProjectWorkflow、Stage、ChecklistItem、ChecklistRecord/Ref；Handover只通过Application Port输出资格
涉及API：冻结WORKFLOW_CHECKLIST_RECORD；本项不挂载Router
权限：ProjectManager、当前ACTIVE Project、Session/CSRF、License；最终由后端重验
验收：明确PASS/FAIL/WAIVED、请求引用、事务锁、幂等/Audit、策略注册与回滚边界
```

## 结论与实现边界

- 2026-10-02 的P01全量阻塞结论不再适用于Handover两项：HND-03已经提供并真实验证当前Approved Version/Review、Document/Evidence/Capability/AI、Action及Trace资格Owner。其他十项Checklist和ApprovedException Owner仍未因此具备。
- 下一实现采用通用Workflow写服务+显式资格策略注册表。首个注册策略仅为`HANDOVER_BASELINE`、`HANDOVER_ISSUES`；未知或尚无Owner的Item失败关闭。Workflow不得直查`hnd_*`，Handover适配器不得写Workflow。
- `PASS`必须在同一调用方事务先调用Handover Owner，再把它返回的Evidence/ReviewRound最小观测写入记录；请求`evidence_refs`必须与Owner合格集合精确一致，禁止任意同项目Evidence拼接。PASS的`exception_refs`必须为空。
- `FAIL`不能推进Gate，可在当前受权事实下追加，但仍须遵循当前Workflow/Stage/Item锁、不可变链、幂等、Audit和乐观版本；不借FAIL绕过身份或写入任意引用。
- `WAIVED`继续失败关闭：当前没有ApprovedException实体/审批/撤销Owner。接口合同存在不等于服务端可以伪造例外。未来实现必须走独立Change Request与真实人工审批Owner。
- Repository固定锁序为Workflow→当前Stage→ChecklistItem→当前记录链；原子追加Record/Refs并将Item状态/Item lock和Workflow lock各加一。业务Owner证明、记录写入、Audit与幂等完成必须同事务；任何失败整笔回滚。
- 客户请求的`result`只是操作意图，不是业务事实。服务端派生并持久化Owner观测的state、lock version、fingerprint、verified_at；客户端不得提交这些证明字段。

## 分解、兼容与验证计划

1. `P07-A02`：实现Workflow-owned追加Repository，覆盖首次/更正链、双版本、Refs、锁顺序、并发与回滚；不接权限/Owner/API。
2. `P07-A03`：实现受权命令与Handover策略注册，Session/CSRF/PM/License、请求引用精确匹配、幂等原结果、Audit故障回滚；WAIVED/未注册Item失败关闭。
3. 后续独立实现冻结HTTP、Windows组合/真实浏览器，再进入Stage Gate/Transition；不跨任务顺手实现。

本项无代码、Schema/Migration、API、权限、依赖、Secret、网络或客户数据变化。原0030/0032及冻结API不改；未注册策略即可回滚而保留历史。验证为冻结合同、现有Schema/查询、HND-03 Owner和旧P01阻塞项的静态交叉核对；不宣称Checklist写、Transition、Gate 3或发行通过。
