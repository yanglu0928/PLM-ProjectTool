# REQ-01-A06-A03：RequirementVersion 授权读取

日期：2026-10-07。结论：`REQ_01_A06_A03_VERSION_READ_PASS`。下一项：
`REQ-01-A07` RequirementVersion 校验。

## 实现与边界

- 新增 RequirementVersion 内部 list/get Service 与 SQLAlchemy Repository；所有当前项目成员均可读取，
  每次读取先重证当前 License、Session 和项目角色，跨项目、不存在资源和异常投影均失败关闭。
- list 按同一 Requirement 的 `version_no` 倒序稳定 keyset 分页，页大小限制为 1～200；摘要只携带
  标识、状态、分类、计数、固定引用、指纹和创建信息，不把完整 statement/rationale 填入列表。
- get 返回不可变版本完整快照，包括正文、来源、验收标准、能力评估、假设、排除项、依赖和 AI Task
  引用；按数据库 ordinal 重建顺序，并核验七类声明计数、顶层连续 ordinal 及两类嵌套 Evidence ordinal。
- 读取仅投影固定 Evidence UUID，不复制 Document locator、正文或内部数据库行 ID；读取不新增 Audit、
  receipt 或 Version，保持纯只读语义。公开 HTTP 留在后续任务，不在本项扩张冻结 API。

## 验证

- Windows 11 / PostgreSQL 18.6：真实 CustomerMember、ImplementationMember、ProjectManager 均可读取；
  列表分页无重漏，详情完整有序；跨项目、坏 Session、License 失效、错资源均拒绝，读前后 Audit、
  receipt、Version 行数不变，Alembic drift 为零。
- 定向 13 项、后端全量 3006 项通过且 3 项既有环境跳过；开发 wheel 共 1142 项，SHA-256
  `010dcc7ccad601dd28eab962cc8389a16264928a2852b2531c83dfdc797e70df`，不是正式发行包。

无 Schema、Migration、公开 API、依赖、Secret、客户数据或外发变化；删除新增读取 Service/Repository、
撤销两项授权策略即可回滚。A06 至此完成；A07～A12、Gate 3、UAT 和正式发行仍待。
