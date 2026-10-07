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

## A02 实施记录（2026-10-07）

- 新增 `req_packages`、`req_requirements`、`req_package_memberships` 及 Migration0111；所有关系均显式
  带 `project_id`，membership 以两个组合外键阻止跨项目组织，移除 membership 不采用级联删除。
- 冻结资料只命名 `PackageState` 而未给出枚举。依据项目业务容器既有状态语义，采用
  `ACTIVE / ARCHIVED / RESTRICTED`，初始仅允许 ACTIVE；该选择记入 DEC-975，后续 Owner 不得静默扩值。
- `Requirement.current_approved_version_ref` 在身份表先保留为 nullable UUID，但 A04 Version 表建立前
  由数据库守卫强制为 NULL；A04 再增加同 Requirement、同 Project 的组合外键。此分步不把悬空 UUID
  或 latest 推断成正式版本。
- A03 Owner 安装前只允许 ACTIVE 初始 INSERT；UPDATE、DELETE、TRUNCATE 全部失败关闭。空历史可降至
  0110，任一新表存在历史即拒绝物理降级。Windows 11 / PostgreSQL 18.6、Alembic drift、后端全量与
  wheel 验证均通过；未开放 HTTP、正式业务 Owner 或 RequirementVersion。

## A03 拆分与 P01 实施记录（2026-10-07）

A03 为避免一个任务同时开放多种状态机，拆为：P01 Package/Requirement 创建；P02 Package元数据与
membership；P03 Requirement元数据及 DEFER/REJECT 决定。P01 新增两类内部创建 Owner、两个不可变
首成功结果表和 Migration0112；通用 receipt 只保存引用，精确首响应由 Owner 自有结果快照保存。
Requirement code 收紧为 64 位 ASCII 业务键并在项目内按大写规范值唯一。创建写在同一事务完成当前
Session/CSRF、项目角色、License、Root、结果、Audit 与 receipt；PM和ImplementationMember可创建，
其他角色失败关闭。尚未开放 Router，也未开放 P02/P03 变更状态。

## A03-P02 实施记录（2026-10-07）

P02 新增 Package PATCH、Requirement membership ADD/REMOVE 三类内部 Owner 和 Migration0113。Package
Root 行锁与 `expected_version` 共同保证每个成功命令只递增一个版本；membership 每次最多200个唯一
Requirement，ADD/REMOVE均要求当前Package为ACTIVE，跨项目、重复加入、不存在关联和旧版本失败关闭。
REMOVE只删除关联，不删除Requirement。状态转换固定ACTIVE与RESTRICTED双向、二者可转ARCHIVED、
ARCHIVED终态。每个成功命令保存完整且规范排序的不可变成员集合快照；幂等重放先重证当前权限，再返回
首次结果，不读取已变化的Root。数据库触发器继续关闭Requirement更新，并重证结果快照与同事务当前
Package/成员集合一致；有命令历史拒降。未开放Router，也未开放P03 Requirement决定。

## A03-P03 拆分与 P01 实施记录（2026-10-07）

P03 拆为P01决策/Evidence历史Schema与P02 Requirement PATCH/DEFER/REJECT/ARCHIVE Owner。P01以
Migration0114新增不可变状态决策及Evidence引用表，固定reason、impact、actor、before/after version，
并以决策+Requirement+Project组合外键和Requirement/after_version唯一约束防归属及版本漂移。
DEFER/REJECT至少一个同项目ELIGIBLE PROJECT Evidence的现时证明、Root转换、不可变首结果与幂等/Audit
留在P02同事务实现；P01写Owner保持关闭，不把空决策或未验证Evidence写成正式事实。

## A03-P03-P02 实施记录（2026-10-07）

P02开放Requirement PATCH/DEFER/REJECT/ARCHIVE内部Owner并新增Migration0115不可变首结果。PATCH仅
ACTIVE改code；DEFER/REJECT仅ACTIVE且必须固定reason、impact及1～100条当前同项目PROJECT/ELIGIBLE
Evidence；ARCHIVE允许任一非归档状态进入终态，不增加未冻结的恢复命令。Root、决策、Evidence引用、
结果、Audit和receipt同事务完成；数据库延迟闭包禁止提交“Root已变但无结果”或“决策无Evidence”的
半套结构。幂等重放返回首成功快照并重证当前权限。A03身份Owner至此完成，仍未开放Router。

## A04 拆分与 A01 编码前核查（2026-10-07）

A04拆为A02 Version primary/正式指针组合FK、A03六类语义owned表、A04 Evidence/AI支持引用与提交完整性。
冻结Domain含title而冻结API最小输入未含title，选择保留nullable物理列但V1不新增必填请求字段；priority
固定LOW/MEDIUM/HIGH/URGENT，risk固定LOW/MEDIUM/HIGH/CRITICAL。版本内dependencies是声明，不替代
A09 RequirementRelation DAG。正式指针在A08前继续关闭；A04不开放业务写或制造Approved事实。
