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

## A06-A02 实施记录（2026-10-08）

新增Requirement当前Approved Version、GLOBAL/同项目PUBLISHED TemplateVersion和GLOBAL/同项目AVAILABLE
DocumentVersion的事务内共享锁证明Port/SQL Adapter；Document沿用Owner Adapter但使用独立Version语义方法，
不滥用Template scope参数。跨项目、非当前批准和非ACTIVE/AVAILABLE状态失败关闭，OutputArtifact仍无Adapter。
Win11/PG18.6隔离证明、Prototype定向47/99 subtests、后端3128/3/4666 subtests、compileall及wheel1200项/
`5b724bb5…60bb09e`通过；无Schema/公开API/依赖/外发，进入DRAFT Create Owner与Schema0131。

## A06-A03 实施记录（2026-10-08）

Migration0131新增不可变Create结果并开放DRAFT Version Owner；Root行锁串行版本链，Artifact/Requirement/
Interaction/Result延迟闭包。Service同事务消费A02证明并写Audit/receipt，OutputArtifact继续失败关闭，正式
批准指针不推进。复用Template安全JSON时首次异常类型不兼容，已转换为Version稳定错误且未放宽规则。
Win11/PG18.6 v1→v2、后端3132/3/4671 subtests、compileall及wheel1203项/
`4ecd8f05…16df41d`通过；进入Read/Validate。

## A06-A04 实施记录（2026-10-08）

新增项目内Version倒序分页/历史Get及不变更状态的ValidationReport；每次重证成员权限/License，Validate重证
Template、当前Approved Requirement与Document可用性并写Audit。首轮PG夹具JSON冒号被SQLAlchemy当绑定参数，
改为显式JSONB参数后重跑，不涉及产品缺陷。Win11/PG18.6、后端3136/3/4684 subtests、compileall及
wheel1205项/`b8ea3055…346ed1c`通过；无Schema/公开API变化，A06完成并进入A07 Review/Formalize。

## A07-A01 前置核查（2026-10-08）

固定`PRT-03 + PROTOTYPE_ALL_V1`复用PROJECT Review Kernel；仅ACTIVE Prototype最新DRAFT可送审，送审及
APPROVE当下重证A06全部当前事实。A07拆为Migration0132窄门、Subject Owner/终态消费、批准Trace Owner和
原子SUBMIT_REVIEW。批准推进正式指针并SUPERSEDE旧批准版；退回/撤回保留旧指针。纯文档PASS，无代码/API。

## A07-A02-P01 实施记录（2026-10-08）

Migration0132新增不可变Review状态结果并开放`PRT-03 + PROTOTYPE_ALL_V1`联合提交窄门。START把最新DRAFT
置为IN_REVIEW并禁止新建后续版；APPROVED推进正式指针且允许旧批准版SUPERSEDE；RETURNED/WITHDRAWN保留
原批准指针。Version、Root、Review/Round、Scope Decision指纹和状态结果由延迟闭包一次核验，裸更新失败。
实现复核补齐同指针Root锁推进与Scope Decision指纹检查，均在正式实库验收前完成。Win11/PG18.6完整状态流、
后端3137/3/4684 subtests及wheel1206项/`0464c7e0…d802952`通过；无公开API/依赖/外发。P02前业务Owner仍关闭。

## A07-A02-P02 实施记录（2026-10-08）

新增Prototype当前事实Validator、真实`PRT-03 + PROTOTYPE_ALL_V1` Subject Owner及PostgreSQL仓储。送审与
批准在同一调用方事务重证Template、当前Approved Requirement、Document及Create规范内容指纹；批准推进正式
指针并SUPERSEDE旧版，退回/撤回保留旧指针。Win11/PG18.6统一Review真实链、输入漂移回滚、后端
3144/3/4684 subtests及wheel1209项/`a30b16ca…827a33`通过；无新Schema/公开API/依赖/外发，进入批准Trace。

## A07-A03-P01 前置核查（2026-10-08）

通用Trace只允许业务Version节点，不能保存Review/Round批准依据；公开TraceCreateService自带UOW，也不能从
Review终态嵌套调用。选择新增Prototype-owned Approval Trace Manifest固定Review/Round/内容指纹和全部来源，
并在同一调用方事务通过Trace低层仓储投影Template/Document DERIVED_FROM及Requirement IMPLEMENTS边。
A03拆为P02 Schema0133、P03 Owner/终态接入；纯文档，不改变冻结API/关系枚举/业务Scope。

## A07-A03-P02 实施记录（2026-10-08）

Migration0133新增不可变Approval Trace Manifest及有序来源表，并以延迟约束要求每个升级后新写APPROVED
状态结果同事务拥有Template/Document/Requirement完整ACTIVE TraceLink集合；错边、缺边、额外边、非批准绑定
和历史改写均失败关闭。旧批准不伪造回填，空Manifest历史可降，有历史拒降。Win11/PG18.6、后端3148/3及
wheel1210项/`10ba4ab5…7f784f`通过；无公开API/依赖/外发，进入应用Owner接入。

## A07-A03-P03 实施记录（2026-10-08）

新增Approval Trace Owner/Repository，并把APPROVED结果、当前事实重证、Template/Document/Requirement三类
业务Version边、0133 Manifest、Prototype正式化、Audit和幂等收据置于统一Review调用事务。非批准终态不投影；
后验重读Manifest及ACTIVE边，重放不重复创建。故障注入证明Trace首写失败时Review决策、Version/Root、结果、
边、Manifest、Audit和收据整体回滚；批准幂等重放再次核验Manifest/ACTIVE边。Win11/PG18.6、后端3153/3、
compileall及wheel1212项/`343e2067…e77992c`通过；无新Schema/公开API/依赖/外发，A03完成，进入原子Submit业务编排。

## A07-A04 实施记录（2026-10-08）

新增固定`PRT-03 + PROTOTYPE_ALL_V1`的Prototype业务送审Service与ProjectManager授权策略；Reviewer锁定、
Review create/start、PrototypeVersion IN_REVIEW绑定、SubjectSnapshot、Audit及持久收据在同一UOW提交。
当前事实漂移零落地，同Key从持久事实重放并重证Owner访问，异载荷冲突。Win11/PG18.6、定向10、后端
3156/3、compileall及wheel1213项/`fe215815…45e557`通过；无Schema/公开HTTP/依赖/外发。A07完成，进入A08 Link。

## A08-A01 前置核查（2026-10-08）

RequirementPrototypeLink固定为独立PROJECT append-only/supersede Aggregate，不以Trace或Version owned ref
替代。CREATE必须同时证明两端当前Approved、PrototypeVersion已有相同RequirementVersionRef、批准Review及
Artifact当前有效；Coverage V1把固定RequirementVersion的AcceptanceCriterion全集精确分为covered与带理由
uncovered且至少一项covered。替换只允许同Requirement/Prototype身份和同purpose，A08拆为Schema0134、
Create/List Owner及Revoke/Supersede Owner；本项纯文档，无Schema/API/外发。

## A08-A02 实施记录（2026-10-08）

Migration0134新增RequirementPrototypeLink表/ORM，以Requirement/Prototype逻辑身份、固定Version和Project
复合FK关闭错端点；purpose/Coverage V1基础形状、ACTIVE逻辑对唯一性、不可逆终态及同身份同purpose且载荷
变化的延迟replacement闭包由数据库保护。首轮不受支持的JSONB函数表达已改为原生减键判空并从新库重跑；
Win11/PG18.6、后端3157/3及wheel1214项/`1ebf51a5…588d94`通过。无公开API/依赖/外发，进入A03 Owner。

## A08-A03 实施记录（2026-10-08）

新增RequirementPrototypeLink内部CREATE/LIST Service与PostgreSQL Repository，补齐四项Link授权策略。CREATE
在同一事务证明当前Approved双端、批准Manifest、owned RequirementRef、A07当前事实及固定需求全部验收条件，
Coverage规范化后精确分区；Link/Audit/receipt原子提交，重放仍重证当前事实，LIST按项目隔离保留历史。首轮
负权限验收预期与既有防枚举合同不符，仅将脚本期望修正为`RESOURCE_NOT_FOUND`后完整重跑。Win11/PG18.6、
定向39、后端3165/3及wheel1216项/`5d5ba5ed…7c7d6a0a`通过；无Migration/公开API/依赖/外发，进入A04生命周期。

## A08-A04 实施记录（2026-10-08）

新增REVOKE/SUPERSEDE内部命令与Repository生命周期操作。REVOKE允许受权人员在业务端点漂移后仍终止ACTIVE
Link；SUPERSEDE只接受同逻辑身份/同purpose和变化后的固定端点/Coverage，重证A03全部当前事实。为兼容
0134 partial唯一键，单一事务先终结旧行并绑定预生成UUIDv7、再插replacement，由延迟闭包在提交时核验；
插入故障证明旧行、Audit和receipt整体回滚。Win11/PG18.6、定向20、后端3170/3及wheel1216项/
`2de46ebe…e8245026`通过；无Migration/公开API/依赖/外发，A08完成，进入A09 HTTP与Windows组合。

## A09-A01 前置核查（2026-10-08）

API-04固定26项Prototype Operation不变。审计确认当前22项已有业务Owner，但Package/Prototype各自LIST/GET
缺授权策略、读Service及Repository，不能用写命令首次结果代替当前受权读取。A09拆为A02补四项Identity
Read、A03五类独立签名cursor、A04 Package HTTP、A05 Identity HTTP、A06 Template HTTP、A07 Version/Review
HTTP、A08 Link HTTP及A09 Windows只读/写组合与真实PG18验收。默认/login-only继续404，Windows平台读写模式
分离；本项纯文档，无Schema/API/代码/依赖/外发，进入A02。
