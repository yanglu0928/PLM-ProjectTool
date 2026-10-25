# PLAN-02-A04-P04-A04-P03-P03：已批准方案输入证明编码前核查

日期：2026-10-26。结果：`PASS_SCOPE_LIMITED`。

## 编码前检查

|项目|结论|
|---|---|
|Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P03-P03`；实现Plan模块内只读、同事务的Approved Solution输入聚合证明。|
|输入基线|冻结Gate 2 DM-05、API-04 `PLAN_VERSION_CREATE`；0170～0177 Plan Schema；CR-SOL-022有向Section/StructuredSpec固定绑定；P02来源Owner核查。|
|前置任务|Plan身份和固定Schema/WBS Trace；SOL-03 Outline Review；SOL-05 Section Review、当前事实/覆盖；SOL-06 StructuredSpec Review/资格。生产PlanVersion创建仍未实现。|
|涉及模块/实体|Plan application；SolutionOutline current root、OutlineVersion、fixed Review snapshot、approved Requirement inventory、Section current/version、StructuredSpec fixed refs及当前资格。只读，不创建PlanVersion。|
|涉及API|无HTTP变更。内部证明为冻结`PLAN_VERSION_CREATE`未来消费的输入；所有引用必须固定版本ID，不接受latest。|
|涉及权限|不自授权。调用者必须已在同一事务完成当前Session、Project、角色及License写入授权；跨项目、撤销或不匹配的来源关闭失败。|
|验收标准|仅当前指针指向的APPROVED Outline可通过；Outline Review必须终态批准且subject/round/version/fingerprint精确匹配；重新证明固定来源和完整Requirement覆盖；收集Outline规定的精确SectionVersion集合及其绑定Spec引用，旧/错项目/重复/缺失/额外/未批准来源失败关闭。无Schema/API/业务写入。|
|风险|同事务本身不保证并发稳定；当前指针Owner需在调用事务中锁定/复查并由后续PlanVersion写Owner同事务消费。SOL-06的审核通过不得被推断为Section整体批准。|

## 兼容性决定（先记录后实现）

- 已证实 `OutlineCoverageProofService` 当前只接收DRAFT验证或DRAFT/IN_REVIEW current-facts；直接用于APPROVED版本会失败。静默跳过该Owner或把历史Validation/Audit当现时证明均不可接受。
- 选择最小内部调整：给已批准路径提供独立且可验证的终态Outline Review证据，再允许只读Coverage Owner在相同事务中复证APPROVED Outline；Plan侧先锁定/读取当前Outline根指针及固定版本，再组合来源、覆盖及Section Spec资格。
- 影响范围：内部 Application DTO/Port/Owner 与单测；不修改 `/api/v1`、DM-05、ORM/Migration、授权策略或业务事实。若发现必须变化冻结合同则停止并另建CR。
- 回滚：移除新聚合Owner及对应内部调用/DTO和测试，恢复Coverage Owner原APPROVED拒绝策略；无数据迁移。
- 验证：通过/漂移指针、Review主体或指纹错误、覆盖缺口、Section未批准、Spec失效、跨项目、重复/增删引用等独立单测；完整后端回归和diff/secret检查。

## 实施与验收结果

- 新增Plan内部 `ApprovedSolutionInputProofService`：同事务校验Outline根当前批准指针、固定Approved版本、Outline PROJECT Review终态身份/轮次/版本/fingerprint；重验Outline固定来源并调用完整覆盖证明；输出精确SectionVersion与StructuredSpec资格引用。Section Spec必须是 `FIXED_REFS` 且逐项取得现时资格，或是已人工声明且有规范化理由的 `NONE_REQUIRED`；`UNDECLARED` 一律失败。
- 扩展 `OutlineCoverageProofService` 的内部 current-facts路径：APPROVED Outline只能附带并匹配已批准终态 Review snapshot 才可复算；旧DRAFT/IN_REVIEW路径和公开接口不变。
- 验证：定向 `26 passed`；完整后端回归 `4107 passed, 3 skipped, 6153 subtests passed`（67.13s）；目标文件 `py_compile` 与 `git diff --check` 通过。
- 范围限制：Owner仍未接入PlanVersion CREATE/HTTP，也未做真实PostgreSQL组合测试；本任务单测通过不证明这些链路。Section/Requirement/Spec当前指针在只读Owner内没有全部持锁；后续原子写Owner必须在同一写事务锁定或复查所有可变当前指针，再落PlanVersion，否则本证明不可单独用于持久化承诺。无ORM/API/Migration或业务数据变化；Pilot/Gate/Release未变化。

下一项：`PLAN-02-A04-P04-A04-P03-P04`，实现消费此证明的PlanVersion同事务DRAFT写Owner，并以实际PostgreSQL验证持久幂等、Audit和所有写入原子性；开始前重新完成该WBS编码前核查。
