# CR-PLAN-010：PlanVersion首版需求覆盖输入与WBS映射

- 日期：2026-10-26
- 状态：`AUTHORIZED_FOR_IMPLEMENTATION_BY_CR-EXEC-001`
- 来源WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P05`浏览器闭环前置核查
- 基线：Gate 2冻结DM-05/API-04；既有`PLAN_VERSION_VALIDATE`与`PLAN_VERSION_SUBMIT_REVIEW` Owner/HTTP；`CR-EXEC-001`持续交付授权

## 差异证据

1. 当前 `ProjectPlanVersionCreateView`只生成一个用户可输入的WBS根任务，固定提交 `requirement_refs: []` 且没有需求排除项输入。
2. Approved Solution固定Outline详情含 `requirement_refs`；现时Validate根据Approved来源形成需求全集，`evaluate_plan_version`对“既未映射到WBS、也未有正式排除决定”的需求返回阻断项 `REQUIREMENT_UNCOVERED`。
3. Plan Review Readiness在同一事务重新证明当前来源/Validate结果；送审不能绕过此缺口。故当前最小UI可创建DRAFT，但当批准Outline含任何需求时，真实Validate/Review闭环必然失败。

## 方案比较与选择

- A：保持单根WBS并把所有需求默认关联根任务。代码量最小，但默认映射会把软件/AI判断伪装成业务分解，且不便维护多项任务。
- B：在不可变Create表单内支持多条WBS根任务；由用户查看固定Approved Requirement版本并显式分配到一条或多条任务；每项已批准需求必须被映射，不能映射/排除的需求则明确显示未覆盖并阻止创建。**选择B**：遵守冻结覆盖规则，不生成AI业务事实，并允许用户明确分解。
- C：允许无映射快照创建并把E2E缩到零Requirement合成方案。拒绝：会掩盖有需求项目不可走通的已知Release质量缺口。

## 范围、影响和回退

- 只扩展现有PlanVersion Create UI及只读候选消费：对每一份Approved Outline的固定RequirementRef进行版本回读并呈现可理解信息；用户逐条分配给本次WBS task；支持多个根任务并保留完整冻结字段。
- 无新增/破坏性API、ORM、Schema、Migration、版本状态、License或权限变化；所有已选Ref仍由现有冻结Create Owner在事务内重新验证。
- 不新增AI自动分配/业务结论、不替用户创建排除/延期决定、不降低服务端Validate/Review规则。当前工作流如要送审，应完成全部Approved Requirement映射；对需要正式排除/延期的范围，本轮Create UI提示尚未支持并失败关闭。
- 将P09-P05拆为 `P09-P05-A01`实现需求覆盖输入，`P09-P05-A02`再进行实际Win11 Edge→PG Create/Read/Validate/Review链路。
- 回退：恢复上一版前端组件即可；无数据库/客户数据迁移，也不会删除任何PlanVersion或Review。新UI测试失败则不集成。

## 验收与风险

- 只读当前Approved Outline的固定Requirement集合；RequirementRef必须精确固定`requirement_id + requirement_version_id`；旧版本、重复、跨Project或不完整读取失败关闭。
- 送Create前确保每个Approved Requirement均分配给至少一项WBS task；每项task保持合法唯一WBS code及完整Acceptance；用户明确确认映射。未支持正式排除时不允许把未映射者静默忽略。
- 定向测试覆盖Requirement详情固定身份/完整性、显式多任务映射、未覆盖阻止、来源刷新/会话路由变化、Create原幂等Payload重试及固定快照读回。完整回归前端全量/typecheck/build和后端Create/Validate/Review合同。
- 主要风险是首次输入比单根任务复杂；用任务模板/逐条需求清单降低录入，但不代替用户作正式分配。正式排除/延期决定需后续SourceDecisionRef输入能力，不在本CR绕过。

## 授权结论

依持续授权与`CR-EXEC-001`，选择B并先记录后实施。此CR仅补足冻结合同已有的Plan Requirement coverage语义，不更改产品Scope、冻结API或数据库基线；原`P09-P02`历史保留。
