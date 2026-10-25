# A06-P05-P04 PlanVersion Review 当前就绪证明前置核查

- 日期：2026-10-26
- 状态：`PRECHECK_COMPLETE`
- 单一目标：为后续 Plan Review Subject 提供同一事务内的当前DRAFT/latest及Review就绪证明；本项不创建Review、分配Reviewer、写状态结果、接HTTP或决定终态。

## 输入与边界

- 冻结 `PLAN_VERSION_SUBMIT_REVIEW` 要求先完成WBS/FS DAG/日期/负责人/验收/覆盖检查；既有 Validate Owner 可重算同一不可变PlanVersion快照，重新验证Approved Solution和来源事实。
- 不可复用旧Validate结果作为当前事实；Start时需重新评估，因此调用范围必须是无副作用的同事务Proof，不能通过嵌套UoW调用公开Validate并单独提交Audit/Receipt。
- `ReviewSubjectProofContext` 持有当前请求Session token与trace_id，仅供服务器端同事务证明；禁止输出、存储或审计Token。
- 创建新PlanVersion的现有Owner首先锁 `PlanRow`。当前就绪Proof必须保证调用者在事务中持有同一Plan身份锁，并再次校验目标为最新DRAFT；并发升版必须串行化。
- 资格范围遵守现有 PROJECT Review/Project authorization 和 Reviewer qualification 服务；本项不重建权限逻辑、不变更角色矩阵。

## 实施前置与验收

新增一个不持久化业务状态的PlanVersion当前就绪证明边界，复用现有纯评估器和Approved Solution/SourceProof依赖；报告必须与精确Project/Plan/PlanVersion、内容指纹及当前时刻绑定。无效、过期/非最新、非DRAFT、来源失效、跨项目、角色/Session失效必须失败关闭。单元测试应证明同事务/固定对象/重证来源/无写入语义；后续Owner真实PG组合证明写事务闭合。

风险：`ValidatePlanVersion._evaluate` 是目前唯一汇合纯规则和当前来源Proof的实现；提取公共只读Proof时必须保持正式Validate响应、Audit、Receipt、幂等语义完全不变。

下一项：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P05` PlanVersion Review Subject创建/Start Owner与0190结果事件同事务落库；本项完成后再按该切片的Owner前置核查继续。
