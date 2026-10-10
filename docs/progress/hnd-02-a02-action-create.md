# HND-02-A02：Action Create Owner

日期：2026-10-05。结论：`HND_02_A02_ACTION_CREATE_PASS`。下一项：`HND-02-A03-A01` Action 状态 Owner 前置核查。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：HND-02-A02
输入基线：DM-05、API-04、Schema0098、CR-HND-001/002、DEC-852/853
前置任务：Action Schema/ORM与初始OPEN事件边界已完成
涉及模块：handover、project、auth、audit、platform idempotency
涉及实体：HND-03 ActionItem Root与首个StateEvent
涉及API：本项不挂HTTP；冻结HND_ACTION_CREATE尚未公开
涉及权限：ProjectManager/ImplementationMember；受理人必须是当前项目有效成员
验收标准：固定Item或显式人工来源、提示完整、Root/Event/Audit/Receipt原子写入、重放并发、失败关闭
风险：自动生成正式待办、登记即确认Item、跨项目受理人、审计失败留下半写、重放越权
```

## 实施结果

- 新增内部Action Create Owner；仅ProjectManager或ImplementationMember可经当前Session/CSRF、License和中央项目授权登记Action。
- 来源必须二选一：同项目固定Analysis Version/Item，或带明确原因的人工来源；分析来源只接受`DRAFT/CANDIDATE`或`APPROVED/CONFIRMED`配对。
- `requested_input_spec`强制1～32个字段并复用Handover字段级名称、格式、示例和必填提示规则；期限必须在服务端事务时钟之后。
- 受理人由Project模块提供当前事实，只接受ACTIVE Project、ACTIVE Department、ACTIVE Membership和ENABLED User。
- Root、唯一seq0 `OPEN`事件、`HND_ACTION_CREATED` Audit及持久幂等收据在同一事务提交；同Key恢复首次不可变视图并重新检查当前Actor权限。
- 人工登记Action不改变Analysis Version或Item状态，不把AI建议或候选项描述为已确认事实。

## 验证与证据

- Windows 11/PostgreSQL 18.6临时库：PM授权、CustomerManager拒绝、当前/禁用/跨项目受理人、AnalysisItem/人工来源、过去期限、License拒绝、同Key冲突、双并发重放、Audit失败整笔回滚和恢复全部通过；临时库已删除。
- 数据库中4个唯一Action、4个seq0事件和4条成功Audit严格对应；来源Item保持`CANDIDATE`，证明创建不等于确认。
- 定向19项、后端全量2621项通过，3项按既定环境条件跳过。
- 最终开发wheel解包定向19项通过，SHA-256 `3c28e90912235cd82cb7323fa2f763b7e82fdabaafd46941ede4b9ff52b62aa9`。

## 兼容、回滚与未关闭项

复用Schema0098和既有依赖，无Migration、公开API、配置、网络或外发变化。停止装配Create Owner即可关闭新写；合法Action/Audit/Receipt历史保留，不删除或降级。

Action状态Owner、Handover Review Subject/正式化、HTTP/UI/Workflow、真实资料质量、正式信任、性能及目标平台发行仍待；本项PASS不代表Action已经响应、验证或关闭，也不代表Gate 3通过。
