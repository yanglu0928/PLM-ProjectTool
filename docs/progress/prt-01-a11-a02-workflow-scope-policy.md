# PRT-01-A11-A02：Prototype Workflow 完整范围策略

日期：2026-10-08。状态：`PRT_01_A11_A02_SCOPE_POLICY_PASS`；不是 Workflow 资格/Checklist/阶段推进 PASS。

纯策略 `prototype.domain.workflow_scope` 消费由后续 Owner 证明的候选：当前 Approved RequirementVersion 及验收标准、显式 NOT_REQUIRED 决定、当前 Approved PrototypeVersion、ACTIVE Link。当前需求完整集合非空，且每条固定版本恰属于“已决定无需原型”或“当前已批准原型”一侧；遗漏、交叉、过期版本、项目不匹配、重复决定、DRAFT/IN_REVIEW、过期正式指针均拒绝。全 NOT_REQUIRED 不是空集合放行，仍要求每条需求有决定。

覆盖规则要求全部需原型的验收标准由精确双端、ACTIVE 的 `VALIDATES/ACCEPTANCE_REFERENCE` Link 已覆盖并集覆盖；`ILLUSTRATES` 和未覆盖原因本身不算通过。多个合法 Link 可互补覆盖，但旧版本、错误项目或撤销 Link 失败关闭。

这是必要条件而非充分条件：候选类型/字符串本身不能证明来源、人工确认、Review、Evidence、固定制品完整性、Trace 或权限。A03 必须由公开 Port 在一个数据库事务内锁定完整范围和全部活动关系并重证这些事实，然后才能生成聚合 Workflow 资格。A04 前只读资格预览的 Prototype 两项仍关闭。

验证：定向 7 项（混合、全 NOT_REQUIRED、空/缺失/交叉、DRAFT/陈旧指针、部分/ILLUSTRATES、跨项目/撤销），后端全量 3218 项运行、3 项条件跳过，全部通过。无 Schema/Migration、运行 API、依赖、Secret 或外发变化。兼容增量与回滚计划见 `CR-PRT-005`；下一项 A11-A03。
