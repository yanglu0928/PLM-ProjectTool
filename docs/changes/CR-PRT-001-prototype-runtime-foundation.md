# CR-PRT-001：Prototype 运行时基础与受控制品边界

日期：2026-10-08。状态：依据 `CR-EXEC-001` 持续授权批准分步实施。Gate 2 原冻结提交
`64cdf09` 保留；本 CR 实现冻结 PRT-01～PRT-05，不把 AI 输出、模板、未校验制品或需求链接描述成
Approved PrototypeVersion。

## 来源、冲突与当前缺口

冻结 Data Model/Schema/API 已定义 PrototypePackage、Prototype、PrototypeVersion、PrototypeTemplate、
RequirementPrototypeLink，API-04 固定 26 个 Operation，并要求 PrototypeVersion 只引用 Approved
RequirementVersion、固定 TemplateVersion 和受控 Artifact。当前仓库没有 `prototype` 模块、`prt_*` 表、
Migration、业务 Owner、Review Subject、Router 或页面；Trace、Audit、AI Task 和 Workflow 中的预留只证明
允许的边界，不构成 Prototype 实现。

实施方案摘要仍列出旧的 `/prototypes/generate`，与 Gate 2 后冻结的项目级资源/版本合同冲突。按仓库优先级
采用冻结 API-04：`PROTOTYPE_GENERATE` 只能经统一 AIService/AITask 产生建议态或 Draft 输入，不另开旧
快捷路径，不执行生成代码，也不能越过 Artifact 校验、人工编辑、Review 和正式指针更新。

## 选择

- 保持 PRT-01～PRT-05 Root、26 个 Operation、角色和错误语义不变；按 Identity/Template/Version/Link/
  Review/HTTP/UI 分层开放，不用一个 generate 命令跨越范围决定、生成、校验和审批。
- PrototypeVersion 采用逻辑身份 + 不可变版本；正式指针只由 `PRT-03 + PROTOTYPE_ALL_V1` Approved Review
  终态消费更新。AI 生成结果保持 Draft，历史版本和固定引用永久保留。
- `NOT_REQUIRED` 是 Prototype Root 上的显式范围决定，必须固定受影响的 Approved RequirementVersion、
  reason、impact、决定/Review 与 Evidence；无 PrototypeVersion 或无 Link 不能被推断为“不需要原型”。
- Template 创建时固定 GLOBAL/PROJECT Scope，修订产生新 TemplateVersion；GLOBAL 模板不得反写项目事实。
  首版只把模板当受控输入，不增加模板市场、任意脚本或执行沙箱。
- RequirementPrototypeLink 两端固定同项目不可变版本，purpose 仅
  `ILLUSTRATES / VALIDATES / ACCEPTANCE_REFERENCE`；覆盖判断同时重验 Link、Version 自带 RequirementRef、
  Artifact 当前可访问性/完整性及 Review，不以任一单表投影代替完整证明。

## 实施拆分

1. `PRT-01-A01`：本 CR、冻结对账、差距及兼容/迁移/回滚计划。
2. `PRT-01-A02`：Package/Prototype identity、membership 与 NOT_REQUIRED decision Schema/Migration。
3. `PRT-01-A03`：Package/Prototype identity Owner、状态、显式范围决定、持久结果与 Audit。
4. `PRT-01-A04`：GLOBAL/PROJECT Template、不可变 TemplateVersion 与 ArtifactRef Schema/Owner。
5. `PRT-01-A05`：PrototypeVersion、Artifact/Requirement/Interaction owned 数据 Schema/Migration。
6. `PRT-01-A06`：Approved Requirement、固定 Template、Artifact/Evidence 证明及 Version create/read/validate。
7. `PRT-01-A07`：`PRT-03 + PROTOTYPE_ALL_V1` Review 送审、终态正式化和 Trace Owner。
8. `PRT-01-A08`：RequirementPrototypeLink Schema、生命周期、覆盖不变量与 Owner。
9. `PRT-01-A09`：冻结 HTTP、Windows 显式组合与真实 PostgreSQL 18 验证。
10. `PRT-01-A10`：前端范围决定、模板选择、制品定位/人工维护提示与真实 Edge 闭环。
11. `PRT-01-A11`：`PROTOTYPE_SCOPE_DECISIONS/PROTOTYPE_COVERAGE` Workflow 资格及相邻推进。

`PROTOTYPE_GENERATE` 的统一 AI Task 接入放在 A06 的 Draft 输入边界内验证；它不是额外公开 Prototype
Operation，也不允许自动正式化。若后续需要新的建议读取/采纳 API，必须单独 CR，不静默扩展 `/api/v1`。

## 迁移、兼容与回滚

- 每个数据库增量必须含 ORM、Alembic up/down、空库与有数据升级、约束负例、drift 和历史拒降。
  无历史可逐级降级；产生 Prototype/Template/Review/Link 历史后拒绝破坏性物理降级。
- 新 Router 默认不装配，直至 Owner 与真实 PostgreSQL 证据完成；冻结 `/api/v1` 只做兼容实现，不改
  path/角色。PATCH 后续必须按冻结控制仅使用强 `If-Match`，不得由服务器伪造幂等 key。
- 应用回滚可移除 Prototype Router、页面、Workflow 注册与 AI Draft 接线，但不得删除历史 Version、
  Decision、Review、Artifact、Link、Trace 或 Audit。
- 无新增依赖、Secret、客户数据外发、License 或目标环境变化。Windows Server 2025 当前未跑本轮链，
  Debian 13 按用户指令跳过；Windows 11 结果不能被外推为其他平台实机通过。

## 验证与关闭条件

逐项执行定向 Unit/API/Permission/Exception、Windows 11/PostgreSQL 18.6 空库/有数据升降级、约束与并发、
真实 HTTP/Edge、完整后端/前端回归、wheel 和 Secret 扫描。A11 之前不宣称 Prototype Workflow 合格；
Gate 3、UAT、发行与可使用程序包仍以各自客观证据关闭。

## A02 实施记录（2026-10-08）

Migration0122新增Package、Prototype、同项目membership、NOT_REQUIRED范围决定及固定受影响
RequirementVersion引用五表。Prototype正式指针先保留nullable，A05 Version表建立前由Owner guard强制
为空；范围决定与子引用在A03原子Owner前全部拒写。空历史可降0121，任何新表历史拒绝物理降级。
Windows 11/PostgreSQL 18.6真实升降、drift、跨项目负例、后端3089/3及wheel1171项/
`ec80a596…57c1d`通过；未开放业务Owner、HTTP或正式Prototype事实。

## A03 拆分与A01前置核查（2026-10-08）

A03拆为A02身份创建、A03 Package修改、A04 Prototype修改、A05 NOT_REQUIRED原子决定。PATCH按冻结控制
仅用强If-Match，不强制幂等key；SET_MEMBERS不级联删除Prototype。PM/CustomerManager实际受权命令本身
构成不可变人工决定，PM动作不称客户确认，可选Review只作附加证明。A05前决定表继续拒写。

## A03-A02 实施记录（2026-10-08）

新增Package/Prototype创建Service、Repository、两个授权Operation及Migration0123不可变首结果。Root、
首结果、Audit和receipt同事务闭合，持久重放只恢复首次View并重证权限。0123拒绝自动接纳Owner关闭期间
可能存在的手工Root，必须另走审计迁移；空历史可降，产生结果后拒降。Win11/PG18.6真实闭环、后端
3094/3及wheel1175项/`36935bcf…25ffb9`通过；Router仍关闭。

## A03-A03 实施记录（2026-10-08）

新增Package PATCH/SET_MEMBERS Service、Repository、授权策略及Migration0124不可变结果。PATCH只改name且
无receipt；SET是允许空集合的全量替换，成员同项目、存在且非ARCHIVED，只删membership不删Prototype。
Root版本、实际集合和结果在提交时延迟闭合。Win11/PG18.6真实闭环、后端3100/3及wheel1178项/
`31875e15…d5f4c5`通过；Router仍关闭。

## A03-A04 实施记录（2026-10-08）

新增Prototype PATCH/ARCHIVE Service、Repository、授权策略及Migration0125不可变结果。PATCH仅在ACTIVE
状态改name且无receipt；ARCHIVE仅PM、单向进入终态并在持久重放前重证权限，不删除Package membership、
Version、Decision、Link或正式指针。Root状态/指针/版本与结果在提交时延迟闭合。Win11/PG18.6真实闭环、
后端3106/3及wheel1181项/`dfb5fe0b…e4108`通过；Router仍关闭，进入NOT_REQUIRED原子决定Owner。

## A03-A05 实施记录（2026-10-08）

新增NOT_REQUIRED原子范围决定Service、Repository、授权策略及Migration0126。决定固定非空当前Approved
RequirementVersion集合；PM/CustomerManager实际受权动作记录confirmed_by但不冒充客户确认。为使可选
Review能证明精确内容，兼容增加32字节decision_fingerprint，并仅接受同项目Approved
`PRT_SCOPE_DECISION` Snapshot精确匹配；Review仍可空，不新增公开请求必填字段。Root、决定、有序引用、
不可变首结果、Audit和receipt同事务闭合。Win11/PG18.6真实闭环、后端3113/3及wheel1184项/
`b88fd092…6c9a6c`通过；Router仍关闭，`PRT-01-A03`完成。

## A04 拆分与 A01 前置核查（2026-10-08）

A04按单一问题拆为A02 Schema0127、A03 PROJECT/GLOBAL Create、A04 Revise和A05内部读取Owner。Create同时
建立Root与不可变首版，Revise仅追加并原子推进当前指针；版本正文只保存非可执行布局/组件合同、适用终端及
固定ArtifactRef。GLOBAL不得引用PROJECT Artifact或反写项目事实；OutputArtifact Owner未就绪时对应引用
失败关闭，不接受裸UUID替代。冻结六个Template Operation、路径和角色不变，HTTP仍在A09统一开放。

## A04-A02 实施记录（2026-10-08）

Migration0127新增GLOBAL/PROJECT Template Root、不可变PUBLISHED Version、有序ArtifactRef及命令结果四表；
布局/组件合同为JSON对象，适用终端有界，Root当前指针以同Template复合延迟FK固定。A03前四表Owner全部
关闭且拒绝TRUNCATE；空历史可降，存在历史拒降。Win11/PG18.6真实升级/升降/drift/约束、后端3114/3及
wheel1185项/`b39bc65e…ae693c84`通过；未开放业务Owner或HTTP。

## A04-A03 实施记录（2026-10-08）

新增PROJECT/GLOBAL Template Create Service、DocumentVersion固定Artifact证明、Repository及Migration0128。
两个Scope使用独立命令和权限；Root、v1 PUBLISHED不可变Version、有序引用、结果、Audit与receipt同事务，
持久重放重证权限/License。合同拒绝主动内容但允许`one`等普通字段；GLOBAL不得引用项目文档，OutputArtifact
Owner未实现时失败关闭。Win11/PG18.6真实闭环、后端3119/3及wheel1190项/
`9ffbb496…84630d`通过；冻结HTTP仍关闭，进入A04 Revise Owner。

## A04-A04 实施记录（2026-10-08）

新增PROJECT/GLOBAL Template Revise Service、锁定Repository及Migration0129。强版本与Root行锁串行修订，
只追加PUBLISHED Version并固定supersedes，当前指针/lock/Actor/ArtifactRef/不可变结果延迟闭合；持久重放仍
重证权限/License。复用Create合同和Artifact证明，OutputArtifact继续失败关闭。Win11/PG18.6真实v1→v3、
后端3123/3及wheel1193项/`7282e72b…4e2ef06`通过；冻结HTTP仍关闭，进入A05 Read Owner。

## A04-A05 实施记录（2026-10-08）

新增Template Read Service/Repository及项目全成员只读策略。项目列表合并同项目PROJECT与GLOBAL，GLOBAL
管理入口只读GLOBAL；keyset分页返回当前固定Version，内部get可读取当前/历史不可变Version并区分
`is_current`、Root ETag及有序ArtifactRef。Win11/PG18.6隔离/分页/撤权闭环、后端3125/3及wheel1195项/
`a82554fb…bd00b8`通过；无Schema/公开HTTP变化，`PRT-01-A04`完成，进入A05 PrototypeVersion基础。

## A05-A01 前置核查（2026-10-08）

固定PRT-03为PROJECT不可变版本：1～100 ArtifactRef、1～200 Approved RequirementVersionRef、固定
PUBLISHED TemplateVersion、每版一条不可执行InteractionSpec及结构化coverage summary全部进入内容指纹。
DRAFT创建不更新正式指针；Review成对引用与状态窄门留A07。OutputArtifact Owner仍缺失，后续Owner对该
类型失败关闭，DocumentVersion可经目标Owner证明。A05拆为A01核查/A02 Schema0130，随后进入A06证明、
Create、Read/Validate；本项纯文档PASS，无Schema/API/外发。

## A05-A02 实施记录（2026-10-08）

Migration0130新增PrototypeVersion、ArtifactRef、RequirementRef和InteractionSpec四表，并以Prototype/
Project、Template/TemplateVersion及Requirement/RequirementVersion复合FK固定归属。Root正式指针只可
指向同Prototype/Project Version；声明计数固定1～100 Artifact、1～200 Requirement、恰一条Interaction。
A06前四表Owner关闭并拒绝TRUNCATE，空历史可降0129，存在历史拒降。首次实库夹具遇到deferred FK pending
event后改为事务局部合成基线并完整重跑；首次全量回归补齐ORM表清单，均未放宽产品约束。Win11/PG18.6、
定向20/21 subtests、后端3123/3/4666 subtests、compileall及wheel1196项/
`f7ec21d7…25b656`通过；无公开API/依赖/外发，进入A06 Owner前置核查。

## A06-A01 前置核查（2026-10-08）

冻结四个Version Operation不变。A06拆为A02固定输入证明、A03 DRAFT Create和A04 Read/Validate；Create在
同一事务重证当前Approved Requirement、固定PUBLISHED Template和AVAILABLE DocumentVersion，OutputArtifact
在正式Owner建立前失败关闭。DRAFT不更新正式指针，Validate只生成报告/Audit不改变状态。AI Task只可提供
建议态输入/来源，不替代Artifact或人工批准。本项纯文档PASS，无Schema/API/代码/依赖/外发。
