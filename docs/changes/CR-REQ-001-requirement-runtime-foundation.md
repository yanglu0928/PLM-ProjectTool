# CR-REQ-001：Requirement 运行时基础与正式来源边界

日期：2026-10-07。状态：依据 `CR-EXEC-001` 持续授权批准分步实施。Gate 2 原冻结提交
`64cdf09` 保留；本 CR 实现冻结 REQ-01～REQ-04，不把 AI Candidate、未批准 Survey 或
`PENDING_CONFIRMATION` 描述成正式需求。

## 来源、冲突与当前缺口

冻结 Data Model/Schema/API 已定义 RequirementPackage、Requirement、RequirementVersion、
RequirementRelation，版本 owned 集合包括 Source、AcceptanceCriterion、CapabilityAssessment、
Assumption、Exclusion、Dependency；API-04 固定 22 个 project-scoped Operation。当前仓库没有
`requirement` 模块、`req_*` 表、Migration、Owner、Review Subject、Router 或页面。

实施方案前段摘要仍列出旧的 `/requirements/analyze` 与 `/requirements/{id}/match`，与 Gate 2 后冻结的
`/api/v1/projects/{project_id}/requirements...` 合同冲突。按仓库优先级采用冻结 API-04；AI
`REQUIREMENT_NORMALIZE/MATCH` 只生成候选或匹配建议，不另开旧摘要 URL，也不能直接更新正式指针。

## 选择

- 保持 REQ-01～REQ-04 Root、22 个 Operation、角色、分类和关系类型不变；先物理化再按 Owner/HTTP/UI
  分层开放，不用一个“analyze”大命令跨越身份、版本、来源、能力判断和 Review。
- RequirementVersion 采用逻辑身份 + 不可变版本；正式指针只由 `REQ-03 + REQUIREMENT_ALL_V1`
  APPROVED Review 终态消费更新。旧版保留并可被 Trace/Evidence/输出反向查询。
- 来源只允许当前证明的 APPROVED SurveyConclusion、确认的 Handover、受权人工正式决定或合格
  PROJECT Evidence；TEMPLATE、AI Task、未批准结论和动态 latest 不能单独成为正式来源。
- 分类固定四值。STANDARD_FUNCTION 至少一个人工 CONFIRMED DIRECT 能力判断；NONSTANDARD_FUNCTION/
  DIFFERENCE 必须有缺口、解决方向和排除；PENDING_CONFIRMATION 禁止提交正式 Review。
- Relation 两端固定同项目 RequirementVersion；DEPENDS_ON/PARENT_OF 防自环和非法环，对称关系规范化，
  revoke/supersede 保留历史。合并拆分创建新版本和 Trace，不覆盖旧事实。

## 实施拆分

1. `REQ-01-A01`：本 CR、冻结对账、差距与兼容/迁移/回滚计划。
2. `REQ-01-A02`：Package/Requirement identity 与 membership Schema/Migration。
3. `REQ-01-A03`：Package/Requirement identity 内部 Owner、状态与持久幂等/Audit。
4. `REQ-01-A04`：RequirementVersion 及六类 owned 集合 Schema/Migration。
5. `REQ-01-A05`：Survey/Handover/人工决定/Evidence/Capability 固定来源证明 adapters。
6. `REQ-01-A06`：Version create/list/get 与不可变指纹、替代链。
7. `REQ-01-A07`：Version Validate 与分类、验收标准、来源/能力/冲突失败关闭。
8. `REQ-01-A08`：`REQ-03 + REQUIREMENT_ALL_V1` Review 送审及终态正式化。
9. `REQ-01-A09`：RequirementRelation Schema、无环、规范端点与生命周期 Owner。
10. `REQ-01-A10`：冻结 HTTP、Windows 显式组合与真实 PostgreSQL 验证。
11. `REQ-01-A11`：前端来源定位/人工输入提示与真实 Edge 闭环。
12. `REQ-01-A12`：`REQUIREMENT_FORMAL_VERSIONS/ACCEPTANCE` Workflow 资格及相邻推进；另行记录
    其事实映射，不在前置 Schema 任务静默开放。

## 迁移、兼容与回滚

- 每个数据库增量必须含 ORM、Alembic up/down、空库与有数据升级、约束负例、drift 和历史拒降。
  无历史可逐级降级；产生 Requirement 历史后拒绝物理降级，采用向前修复或备份恢复。
- 新 Router 默认不装配，直至 Owner 与真实 PG 证据完成；冻结 `/api/v1` 仅做兼容实现，不改 path/角色。
- 应用回滚可移除 Requirement Router/页面/Workflow注册，但不得删除版本、Review、Evidence、Trace、Audit。
- 无新增依赖、Secret、客户数据外发、License 或环境目标变化；Windows Server 2025 与 Debian 13 仍按
  当前发布策略处理，不能由 Windows 11 结果自动宣称实机通过。
