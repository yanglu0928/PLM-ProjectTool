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

## A04-A02 实施记录（2026-10-07）

Migration0116新增RequirementVersion primary，版本号在同Requirement内唯一，替代链以Version、
Requirement、Project复合外键固定同父同项目并禁止自替代；partial unique index分别限制最多一个
IN_REVIEW和APPROVED。Requirement当前批准指针增加同样三列复合外键，但既有Root守卫继续禁止其变化，
直至A08正式化Owner原子更新。全部Version写在A03/A04/A06完成前失败关闭。空历史可降0115，有Version
历史拒绝降级；Windows 11/PostgreSQL 18.6真实升降、drift、负例、关闭守卫和历史保护通过。

## A04-A03 实施记录（2026-10-07）

Migration0117按冻结名称建立Source、AcceptanceCriterion、CapabilityAssessment、Assumption、Exclusion、
Dependency六类Version owned表，全部显式携带Version/Requirement/Project复合归属和有序ordinal。
AcceptanceCriterion物理要求可观察结果、验证方法、数据、环境和Evidence要求；CapabilityAssessment精确
FK固定GLOBAL CapabilityVersion/Item，AI Candidate只能保留CANDIDATE状态，不能伪装人工确认。
Dependency仅为版本声明而非A09关系图。Evidence/AI支持引用与声明计数提交闭包留A04；六表业务Owner
继续关闭。空历史可降0116，有owned历史拒降；Win11/PG18.6真实升降、drift及负例通过。

## A04-A04 实施记录（2026-10-07）

Migration0118新增Source/Assessment Evidence和Version AI Task三类规范化支持引用，并以延迟constraint
trigger在提交时核对七类声明计数、连续ordinal、CapabilityAssessment的GLOBAL STANDARD+同Project
PROJECT双证据、PROJECT_EVIDENCE Source同一映射，以及AI Task已接受到当前requirement Draft。三类
support Owner继续关闭。0118允许既有身份历史升级，但拒绝自动接纳此前关闭Owner期间由管理员绕过产生
的Version行，必须另走审计迁移。A04 Schema至此完成；来源对象资格与当前状态由A05 adapter证明。

## A05 拆分与 A01 编码前核查（2026-10-07）

A05拆为A02 SurveyConclusion/Handover、A03 PROJECT Evidence/Capability、A04 Human Decision与五类
真库闭环。Survey与Handover必须同时证明业务当前状态和统一Review终态；Evidence与Capability由各自
Owner在调用方事务内共享锁读取当前资格。现有人工正式决定权威载体仅有Requirement A03创建的不可变
DEFER/REJECT Decision及Evidence/首结果闭包，因此首版`HUMAN_DECISION`只接受该范围；未实现的范围排除、
风险接受和通用例外不能由备注、Handover Action或通用Review状态推断。

## A05-A02 实施记录（2026-10-07）

Survey与Handover所属模块新增Requirement专用只读proof adapters；除业务Root/Version当前状态外，同时
联查精确APPROVED Review、Round及Review Subject Snapshot的subject/version/content fingerprint。
所有事实在调用方事务内共享锁定，输出仅含固定身份、审批引用、版本号和隐藏指纹，不复制正文或位置。
Win11/PG18.6跨项目、错版本、指纹漂移、受限Root和零写验证，后端2986/3及wheel1131项通过；无Schema、
公开API、依赖、Secret或外发变化。

## A05-A03 实施记录（2026-10-07）

Evidence专用proof复用当前PROJECT/ELIGIBLE共享锁仓储，只输出固定Document/Version、lock version与隐藏
指纹；Capability proof锁定ACTIVE GLOBAL Baseline当前APPROVED Version及AVAILABLE Item，并绑定精确
GLOBAL Review/Round/Snapshot。Win11/PG18.6跨项目/错Item、Evidence撤销、Snapshot漂移和零写验证，
后端2990/3及wheel1135项通过；无Schema、公开API、依赖、Secret或外发变化。

## A05-A04 实施记录（2026-10-07）

Requirement模块新增Human Decision专用proof，在调用方事务内共享锁定同项目不可变DEFER/REJECT决定、
首成功命令结果及精确Evidence集合，并重证operation、reason、impact、前后版本和最终状态一致。五类来源
随后在同一事务完成真库闭环；当前PROJECT Evidence撤销会阻止新的当前来源证明，但不追写既有人工决定
历史。错配负例保持数据库合法shape并替换错误Evidence UUID，证明失败来自adapter集合核验而非数据库
非空约束。Win11/PG18.6跨项目、错配、撤销、零写与drift，定向24、后端2992/3及wheel1137项通过；
无Schema、公开API、依赖、Secret或外发变化。A05至此完成，进入A06。

## A06 拆分与 A01 编码前核查（2026-10-07）

A06拆为A02原子创建和A03授权list/get。创建必须显式initial且无历史，或以固定base_version_ref精确指向
当前最高版本；同事务锁定ACTIVE Requirement、递增Root ETag、重证A05来源及Evidence/Capability并一次
写完Version、owned/support集合、Audit、receipt。内容指纹只覆盖规范化业务快照和固定引用。0118要求AI
Task已接纳到最终Version ID，但冻结create未提供客户端Version ID或跨Owner预接纳协议；首版只接受空AI
Task集合，后续扩展须独立CR，不绕过闭包。A03列表使用version_no稳定keyset，get返回完整有序固定快照。

## A06-A02 实施记录（2026-10-07）

新增原子DRAFT创建Service/Repository与Migration0119：显式initial或精确当前最高base、ACTIVE Root行锁及
ETag共同防分叉；Version、六类owned、支持引用、不可变首结果、Audit和receipt同事务闭合。0119以创建
结果分别闭合Root bump和每个Version，全部版本内容仍不可改删/截断。内容指纹排除initial/base/ETag/
client reason等命令元数据；请求幂等指纹保留这些字段。由于跨Owner AI预接纳协议尚不存在，非空AI Task
及AI_CANDIDATE assessment均失败关闭，只接受HUMAN assessment。Win11/PG18.6升降、drift、真实权限、
Evidence、幂等、并发、回滚、直写拒绝和历史拒降通过；定向33、后端3000/3及wheel1140项通过。

## A06-A03 实施记录（2026-10-07）

新增RequirementVersion授权list/get内部读取Owner。列表在同一Requirement下按`version_no`倒序keyset，
仅返回摘要；完整statement/rationale和七类固定集合只在详情返回。详情重证声明计数、顶层连续ordinal及
Source/Assessment两类嵌套Evidence连续ordinal，异常投影失败关闭。CustomerMember、ImplementationMember、
ProjectManager均可读，但每次调用重证当前License、Session和项目成员资格；跨项目隐藏为资源不存在。
Win11/PG18.6验证分页、完整顺序、隔离、拒绝和零写，定向13、后端3006/3及wheel1142项通过。无Schema、
Migration、公开API、依赖、Secret或外发变化；A06完成，进入A07 Version校验。

## A07 实施记录（2026-10-07）

新增RequirementVersion共享锁快照、当前事实Validator、幂等报告Owner及Audit回放proof。每个新Key复算
内容指纹/七类计数/有序集合，重证五类来源、Capability与双侧Evidence，并按冻结规则检查分类、五要素
AcceptanceCriterion及声明冲突。STANDARD要求人工CONFIRMED DIRECT；NONSTANDARD/DIFFERENCE要求人工
CONFIRMED PARTIAL/NONE和明确排除；PENDING始终未通过。业务校验失败仍是成功报告操作，不改变Version；
原Key恢复首次Audit，新Key重验当前事实。Win11/PG18.6漂移/恢复/重放/拒绝/零状态迁移，定向14、后端
3013/3及wheel1145项通过；无Schema、Migration、公开API、依赖、Secret或外发变化，进入A08。

## A08 拆分与 A01 编码前核查（2026-10-07）

A08拆为A02-P01 Review生命周期Migration0120和A02-P02 Requirement Subject Owner。复用通用PROJECT
Review，固定`REQ-03 + REQUIREMENT_ALL_V1`，不新增第二套Review表。只允许ACTIVE Requirement最新DRAFT
送审；送审和APPROVE均在调用方事务重跑A07 CurrentValidator，历史Validate Audit不能替代当前证明，
PENDING或任一来源/能力/Evidence漂移均拒绝。APPROVED原子更新Root正式指针并SUPERSEDE旧正式版；
RETURNED/WITHDRAWN映射Version RETURNED且保留旧指针。HTTP/生产组合留A10，前端留A11。

## A08-A02-P01 实施记录（2026-10-07）

Migration0120开放Requirement Review最小状态窄门和延迟完整性，绑定`REQ-03 + REQUIREMENT_ALL_V1`、
PROJECT、同项目Subject/Version、活动Round、终态及唯一正式指针。实施时确认Requirement Root在0115/
0119已有每次ETag变更必须绑定不可变结果的强闭包；直接仿照Survey会被迫放宽保护。按持续授权新增内部
`req_requirement_review_state_results`，固定Review事件、前后正式指针、Actor和lock version，并反向闭合
Root与Version状态转换。无结果直写、改删/截断失败关闭；有Review历史拒降。Win11/PG18.6升降/drift、
START/RETURNED/APPROVED，定向20、后端3014/3及wheel1146项通过；P02前Owner仍关闭。

## A08-A02-P02 实施记录（2026-10-07）

新增Requirement Review Subject Owner与PostgreSQL Repository，复用PROJECT Review内核并固定
`REQ-03 + REQUIREMENT_ALL_V1`。Create/Start只接受ACTIVE Root最新DRAFT，Reviewer重证当前项目成员；
Start和APPROVED在同一事务重跑A07 CurrentValidator，RETURNED/WITHDRAWN不把过期来源误作批准前提。
Repository写Version、Root及0120不可变结果后主动flush，终态断言同时重读结果、正式指针、唯一APPROVED
和lock version；每个终态另写Requirement Audit。Win11/PG18.6验证来源漂移拒绝、两次批准、旧正式版
SUPERSEDED及RETURNED保留指针，定向14、后端3019/3及wheel1148项通过。无Schema、公开API、依赖、
Secret或外发变化；A08完成，进入A09 RequirementRelation。

## A09 拆分与 A01 编码前核查（2026-10-07）

A09拆为A02 Migration0121、A03 create/list Owner、A04 revoke/supersede Owner。REQ-04继续使用独立
`req_relations`而非拿通用TraceLink代替；物理端点保存source/target Requirement与Version组合键，以同项目
复合FK证明固定版本。DUPLICATES/CONFLICTS_WITH按`(requirement_id,version_id)`UUID字节序规范化，
RELATED_TO按冻结基线保留方向；DEPENDS_ON、PARENT_OF分别在同关系类型ACTIVE子图防自环/成环，不把
Version内文本dependency推断成边。所有写先通过Project写授权并锁Project行串行化图变更；Schema只约束
shape/不可变生命周期，递归图证明由同事务Owner完成。无公开API、Schema或运行代码变化，进入A02。

## A09-A02 实施记录（2026-10-07）

新增Migration0121与`RequirementRelationRow`：两端使用Version+Requirement+Project复合FK，五类关系、
三态/lock shape、非自关系、DUPLICATES/CONFLICTS_WITH规范顺序、同项目replacement及ACTIVE唯一/
双向邻接索引均由数据库约束。Trigger只允许初始ACTIVE和一次ACTIVE→REVOKED/SUPERSEDED，拒绝内容
改写、删除与截断；有历史拒降。DAG递归和Project串行锁按A01边界留A03/A04 Owner，不以Schema虚报。
Win11/PG18.6升降/drift及全部正负例、定向21、后端3020/3、wheel1149项通过；首轮全量唯一失败是既有
RAG随机密文末字节恰为固定替换值导致的无实际篡改，独立10次与完整复跑通过，未跨WBS修改RAG。

## A09-A03 实施记录（2026-10-07）

新增RequirementRelation create/list Service与Repository并补齐四项冻结授权策略。写命令在Project写授权
取得行锁后证明两端组合身份、规范化对称端点、按DEPENDS_ON/PARENT_OF分别递归防环，并以ACTIVE唯一
边提供自然幂等；Idempotency receipt、Audit和边写入同事务。列表由任一当前项目成员读取，以UUIDv7关系
ID倒序keyset分页且仅限项目。Win11/PG18.6真实Session/CSRF/License/角色、反向对称输入、分页、端点
错配、类型DAG和两位Actor并发互补边通过；定向12、后端3025/3及wheel1151项通过。无Schema、公开API、
Secret或外发变化，进入A04 revoke/supersede。

## A09-A04 实施记录（2026-10-07）

在同一Relation Service/Repository新增revoke与supersede：两者复用License、Session+CSRF、冻结角色、
Project行锁、receipt和Audit。Supersede共享锁旧ACTIVE边，从递归DAG中排除旧边后证明replacement；可
创建新边或复用另一条既有ACTIVE边，再原子将旧边单向终结。Revoke只允许ACTIVE→REVOKED；原Key从
receipt回放固定终态，新Key对终态失败关闭。Win11/PG18.6验证反向替代、既有replacement复用、终态拒写、
Audit/receipt/drift，定向14、后端3027/3及wheel1151项通过；首轮仅验收脚本把重放误计为新receipt，
修正6条后新库复跑。A09完成，进入A10 HTTP/Windows组合。

## A10 拆分与 A01 编码前核查（2026-10-07）

冻结22个Requirement Operation当前均未挂HTTP。17个普通内部行为可复用；缺Package/Requirement四个
读取Owner及`REQ_VERSION_SUBMIT_REVIEW`原子业务外层。A10拆为A02 identity读取、A03 Package HTTP、
A04 Requirement identity HTTP、A05 Version普通HTTP、A06原子送审、A07 Relation HTTP、A08 Windows
显式组合与真实PG。四类列表使用相互独立且用途绑定的cursor；Relation revoke/supersede在A07补齐冻结
API-01强If-Match承接。A08同时把Requirement Subject注册到通用PROJECT Review决定组合，否则业务送审
后不能安全完成批准/退回/撤回。A01仅静态核查，无Schema、公开API、依赖、Secret或外发变化。

## A10-A02 实施记录（2026-10-08）

新增Package/Requirement identity授权读取Owner与PostgreSQL Repository，落实四个冻结
Operation的当前Project Member读取策略。两类列表均按`(updated_at,id)`倒序成对keyset；
Package详情对成员ID按UUID字节序稳定排序，Requirement投影仅含当前状态、正式版指针与
ETag。读取不写Audit/receipt或业务表，异常仓储shape失败关闭。Windows 11/PG18.6真实
库的成员读取、双页keyset、成员顺序、隔离、拒绝、零写/drift通过；定向13、后端
3033/3和wheel1153项/`6736871a…a7621`通过。无Schema、公开HTTP、依赖、Secret或外发变化。

## A10-A03 子项拆分（2026-10-08）

A03公开边界检查发现内部Package PATCH强制幂等key，与冻结API-04的`S,L,C,M,A`
冲突。已先登记`CR-REQ-002`，将A03拆为P01 PATCH内部合同对齐和P02六个HTTP。
P01移除PATCH key/receipt，保留If-Match、不可变command result和同事务Audit；ADD/REMOVE持久
幂等不变。Win11/PG18.6、定向6、后端3033/3及wheel1153项/`c52ddd2b…e324`通过。
