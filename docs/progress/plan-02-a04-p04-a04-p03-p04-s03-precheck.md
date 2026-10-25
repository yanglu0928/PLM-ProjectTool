# PLAN-02-A04-P04-A04-P03-P04-S03：PlanVersion DRAFT 聚合写入前置核查

日期：2026-10-26。结果：`PRECHECK_ADJUSTED / INPUT_CONTRACT_DETAIL_GAP`；未开放写口、未写业务数据。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P03-P04-S03`；原目标为消费 Approved Solution Proof、创建完整 PlanVersion DRAFT 聚合|
|输入基线|Gate 2 冻结 DM-05/API-04、CR-PLAN-002方案C、Migration 0186、S02 Schema记录、P03 Approved Solution Proof|
|前置任务|Plan身份创建与读取、Approved Solution来源证明、完整快照Schema均已具备；来源证明为只读单测Owner，未锁定全部来源指针|
|涉及模块/实体|Plan application/domain/repository；PlanVersion、WBS、FS依赖、Milestone、排除与typed child rows；ProjectMember与固定Solution/Requirement引用|
|涉及 API|本片不挂载HTTP；未来目标为冻结 `POST /api/v1/projects/{project_id}/plans/{plan_id}/versions`，不得改变合同或接受未知字段|
|涉及权限|仅 `PROJECT_MANAGER`/`IMPLEMENTATION_MEMBER` 可创建；在事务内重验Session/CSRF、Project、成员/角色、License与Plan ACTIVE 状态|
|验收标准|输入载荷严格类型化/规范化与完整校验；稳定指纹；固定批准来源及跨项目引用拒绝；Owner原子写入全部聚合、幂等收据、Audit；失败回滚；实际PG约束/并发/回放验收|
|风险|只读来源证明不足以抵御并发指针漂移；API文档未给字段级类型/上限/响应快照规则；OutputArtifact目标不存在；循环依赖、遗漏映射或未知字段可能造成丢失/伪造业务事实|

## 代码事实与范围调整（先记录后实现）

- API-04只定义PlanVersionInput/WbsItemInput的语义字段摘要；仓库不存在可执行的 `PlanVersionInput`、`WbsItemInput`、`DependencyInput` 或 `MilestoneInput` 类型。因此直接实现持久化Owner将迫使实现者自行猜测字段类型、边界、规范化与请求指纹规则。
- 已有Plan身份创建Owner具备事务授权、通用幂等收据、首次结果重读与Audit模式；可作为实现参考，但版本请求重放必须确保响应由不可变完整快照重建，不能只回PlanVersion ID。
- `ApprovedSolutionInputProofService` 组合当前批准Outline/Section/Spec证明，但本身只读；既有核查明确指出Plan写事务需锁定或同事务复查Outline及所有可变来源当前指针。不能把此前只读单测误当作原子写入前置已满足。
- Migration 0186已将Schema扩至完整快照首片，仍未定义类别/协作角色/Calendar业务白名单；由Plan Owner受控registry验证。非空 `output_refs` 继续失败关闭。
- 因此将S03拆为独立子片：`S03-P01` 定义严格、未知字段拒绝的完整输入/结果模型与纯校验/规范化/指纹；通过后再进行 `S03-P02` 同事务持久化Owner、来源复核、幂等与Audit。HTTP/平台装配仍需单独WBS，不在这两个子片中顺手开放。
- 兼容性：仅细化内部实现顺序，不改变Gate 2冻结的外部路径、语义字段、权限或Scope；与CR-PLAN-002方案C一致。若字段级规则无法从冻结资料推出，先按失败关闭并记录具体实现差异，不增加业务承诺。

## 当前结论与下一项

- 本片为源码/冻结合同核查，不含代码、Schema、API、依赖或数据变化；未运行功能测试。
- `S03-P01` 编码前输入：逐项映射冻结PlanVersionInput、WbsItemInput、DependencyInput、MilestoneInput与0186 ORM；定义精确UUID/枚举/文本上限/有序集合规则、未知字段拒绝和确定性fingerprint；非空output refs拒绝；以独立unit tests覆盖validation、重复/排序、层级/环等结构性负例。此片无SQL写入。
- Pilot、Gate 3、正式Release维持原状态。
