# CR-SUR-001：Survey 运行时基础与实际调研事实边界

日期：2026-10-06。状态：依据 `CR-EXEC-001` 持续授权批准分步实施。Gate 2 原冻结提交
`64cdf09` 保留；本 CR 不代表任何客户调研、客户确认、Survey Gate、Gate 3 或 UAT 已通过。

## 来源与当前差距

冻结 DM-05、SC-01/02/03 与 API-04 定义 SRV-01～SRV-05 五个 PROJECT Root、十七张
Root/owned table 和二十九个 `/api/v1` Operation。当前运行仓库没有 `survey` 模块、`srv_*`
表、Owner、Router、页面或生产组合；Audit、Trace 和 AI 中的 Survey 类型仅为允许列表，不能代替
业务 Owner、授权、正式 Review 或 Workflow 资格证明。

冻结基线只固定了 `srv_question_source_refs` 的逻辑用途，未固定 Handover Item、Capability Item、
TEMPLATE DocumentVersion 与人工来源在单表中的列和约束；也没有规定五个 Root 应在同一迁移还是
分批交付。若把动态 latest、目录路径、正文副本或无类型 UUID 写成来源，将失去版本、Scope、
ProjectId、授权和反向追溯。若一次迁移实现定义、轮次、答复和结论，又会跨越多个独立状态机与
事务边界，违反“一项 WBS 一个明确问题”。

## 选择

- 保持冻结的五个 Root、十七张表、二十九个 Operation、角色和 `/api/v1` 路径不变。
- `srv_question_source_refs` 使用受控 `source_kind` 和类型化引用；TEMPLATE 只能固定到明确的
  DocumentVersion 并用于问题结构，不能成为 Response、Answer、Conclusion 或 Gate 的客户事实。
- 实际面对面调研以 `PROJECT_RECORD` 的固定 DocumentVersion/Evidence 为来源；实施人员结构化录入时
  固定 `response_source=FACILITATED_RECORD`、记录人、原始 Evidence 和追加式更正链，不伪装成客户自填。
- AI 只能形成建议或 Draft。进入 SurveyVersion、Round 或 Conclusion 的业务内容仍需受权人员明确操作；
  Approved Review 之前不得成为正式 Requirement 来源或 Workflow PASS。
- 五个 Root 按定义版本、执行轮次、分派答复、结论版本分批物理化；跨模块只经公开 Owner Port，
  不允许 Survey 直写 Document、Evidence、Handover、Capability、Review、Trace、Workflow 或 AI 私有表。

## 实施拆分

1. `SUR-01-A02`：新增 SRV-01/SRV-02 六表定义基础与 Migration `20261006_0103`；只建立
   Survey identity、不可变 SurveyVersion、Question/Option/Source/TargetDepartment，Owner 未开放前关闭写入。
2. `SUR-01-A03`：实现 Survey identity、完整 Draft Version 创建与 Validate Owner；服务端计算内容指纹，
   对 Handover/Capability/TEMPLATE/人工来源执行类型和 Scope 证明，保留 Audit 与持久幂等。
3. `SUR-01-A04`：接统一 Review Subject/送审/终态消费；只有实际 APPROVED 版本更新正式指针。
4. `SUR-02`：独立物理化并实现 SRV-03 Round 与 `srv_round_source_records`，固定已批准 SurveyVersion、
   计划/开放/关闭/取消状态和正式现场记录。
5. `SUR-03`：独立物理化并实现 SRV-04 Assignment/Response/Answer/Evidence、更正链、提交/校验/退回；
   `CLOSED` Round 拒绝新答复，同 Round/部门/受访者使用冻结的 `NULLS NOT DISTINCT` 唯一语义。
6. `SUR-04`：独立物理化并实现 SRV-05 Conclusion、分部门/模块结论、Evidence/冲突/待办引用及 Review；
   只有 VALIDATED Response 或合格 PROJECT_RECORD 可成为结论来源。
7. `SUR-05`：按冻结 Operation 分批接只读/写 HTTP、Windows 显式组合、前端 Evidence 定位与输入提示。
8. `SUR-06`：接 `SURVEY_ACTUAL_SOURCES`、`SURVEY_CONCLUSION` 真实资格 Owner、Stage Transition 和
   PostgreSQL/浏览器闭环；不得以空集合、模板、AI 建议或客户端 PASS 放行。

## 迁移、回滚与验证

每个数据库增量同时提供 ORM、Alembic up/down、空库与有数据升级、drift、约束负例和历史拒降。
空历史可逐级降级；产生对应 Survey 历史后拒绝物理降级，改为向前修复或恢复备份。应用回滚可停止
Survey Router/Owner 注入，但不删除历史、Evidence、Review、Trace 或 Audit。

本 CR 只记录实现映射和顺序，不修改冻结业务语义；`SUR-01-A01` 仅完成静态核查。真实客户资料导入、
客户答复/确认、质量、性能、正式信任、Windows Server 2025、Gate 3、UAT 和发行需各自证据关闭。

## 实施记录

- 2026-10-06 / `SUR-01-A02`：完成六表定义基础与 Migration 0103。来源采用真实外键加受控类型，
  TEMPLATE 仅允许模板类别并继续不得作为客户事实；无冻结 API 或 Scope 变化。空历史可降级，存在
  Survey 历史时拒绝降级。Windows 11 / PostgreSQL 18.6、2783 项后端回归及 Wheel 内容检查通过。
- 2026-10-06 / `SUR-01-A03-P01`：完成内部 Survey identity 创建 Owner，按冻结合同允许
  ProjectManager/ImplementationMember，接入当前 Session/CSRF、Project、License、Audit 与持久幂等；
  未开放 HTTP 或创建 Version。Windows 11 / PostgreSQL 18.6、2785 项后端回归及 Wheel 检查通过。
- 2026-10-06 / `SUR-01-A03-P02-A01`：编码前核查发现现有 Handover/Capability 公共投影缺少 0103
  类型化外键所需的版本内 row identity；登记 CR-SUR-002，先由来源 Owner 提供最小证明 Adapter，再写
  SurveyVersion，避免 Survey 直连其他模块私有表。
- 2026-10-06 / `SUR-01-A03-P03`：完成内部 Validate Owner。对不可变快照复算指纹/计数，以有界
  ConditionRule V1 检查题型、较早问题引用与环，并重新证明四类来源和目标部门当前性；报告经 Audit 与
  持久幂等固定，不修改 Version、不开放 HTTP。
- 2026-10-06 / `SUR-01-A04-A01`：Review前置核查确认复用通用PROJECT内核；先以0105开放受控
  Version/Root终态投影，再实现`SRV-02 + SURVEY_ALL_V1`真实Subject Owner。历史Validate报告不能替代
  送审/终态调用方事务内的当前事实重证。
- 2026-10-06 / `SUR-01-A04-A02-P01`：完成 Migration 0105。未新增表列，只开放
  `DRAFT -> IN_REVIEW -> APPROVED/RETURNED`及旧批准版`SUPERSEDED`的窄状态门；延迟触发器强制
  `PROJECT + SRV-02 + SURVEY_ALL_V1` Review/Round、Version和Root正式指针同事务收敛。空历史可降至
  0104，有正式指针、非DRAFT状态或Review引用时拒降；Windows 11/PostgreSQL 18.6及全量后端通过。
- 2026-10-06 / `SUR-01-A04-A02-P02`：完成真实 `SRV-02 + SURVEY_ALL_V1` Subject Owner 与仓储；
  Validate/Review 共用当前定义验证器，送审与批准重验评审人、内容和四类来源，批准原子取代旧版并更新
  正式指针，退回/撤回保留旧正式版。通用 Review basis 不支持 Survey 类型化来源，故不伪造 Evidence/Trace
  引用，改由内容指纹及同事务持锁重验保证当前性；未来扩展 basis 类型须另走 CR。无 Schema/API/依赖/
  外发变化；Windows 11/PostgreSQL 18.6、后端全量及 wheel 检查通过。
- 2026-10-06 / `SUR-01-A04-A02-P03`：确认冻结PROJECT Review四写Router按Subject调度，`SRV-02`
  直接复用而不复制Survey专用Review路径；新增`SURVEY_ALL_V1`创建/开轮/终态、安全边界和错误投影合同。
  无运行时代码、Schema/API路径/依赖/外发变化；后端全量及wheel检查通过，真实Windows HTTP/PG组合留P04。
- 2026-10-06 / `SUR-01-A04-A02-P04`：P03预想的第二份同路径Router无法与既有Handover入口安全共存，
  因此登记并实施CR-SUR-003，以Review-owned Subject Registry让唯一PROJECT Router按`HND-02`/`SRV-02`
  失败关闭分派。Windows 11/PostgreSQL 18.6真实Survey与Handover双链、后端全量和wheel通过；无Schema/
  冻结API/依赖/外发变化，默认/login-only/只读组合仍关闭Review写入。
- 2026-10-06 / `SUR-01-A05-A01`：盘点冻结Survey定义10个Operation；内部已有CREATE、VERSION_CREATE、
  VERSION_VALIDATE与通用Review链，但Survey Router、读取、metadata状态和原子SUBMIT_REVIEW仍为零。按读取、
  状态、普通写HTTP、原子送审、读HTTP及Windows组合六项拆分；纯文档，无运行行为变化。
- 2026-10-06 / `SUR-01-A05-A02`：完成Survey/Version四读内部Owner与Survey-owned仓储；四类Project成员
  每次重验License/Session/当前成员事实，Survey使用完整双字段keyset、Version倒序分页，详情只展开当前
  Project内的不可变问题结构与类型化固定引用，不跨模块复制正文或路径。无Schema/API/依赖/外发变化；
  Windows 11/PostgreSQL 18.6、2823项后端全量及wheel检查通过。
- 2026-10-06 / `SUR-01-A05-A03`：按CR-SUR-004新增Migration0106和Survey metadata/归档内部Owner；
  只开放ACTIVE名称修改与单向归档，双层IN_REVIEW栅栏、强ETag、双角色PATCH/仅PM归档、Audit及归档
  持久幂等同事务失败关闭。无新表列或冻结API变化；Windows 11/PostgreSQL 18.6、2829项后端全量及
  wheel检查通过。
- 2026-10-06 / `SUR-01-A05-A04`：新增默认关闭的Survey五个普通写Router，严格将冻结
  CREATE/PATCH/ARCHIVE/VERSION_CREATE/VERSION_VALIDATE转换至已验证Owner；四类来源使用显式可空的
  类型化固定字段，不返回跨模块正文/路径。无Schema/依赖/外发变化；定向17、后端2832/3及
  wheel检查通过，真实Windows HTTP/PG组合留A07。
- 2026-10-06 / `SUR-01-A05-A05`：新增Survey业务原子送审Service与默认关闭Router，在单事务复用
  PROJECT Review创建/首轮内核和真实`SRV-02` Owner；同键重放首次Round并重验访问。冻结请求的
  `due_at`/`submission_note`因通用Review无持久化位置，按CR-SUR-005保留字段但V1只接受null，避免
  静默丢弃。无Schema/依赖/外发变化；Win11/PG18.6、定向19、后端2838/3及wheel检查通过。
- 2026-10-06 / `SUR-01-A05-A06`：新增默认关闭的Survey四读Router及两类会话/Project/查询/父资源
  绑定HMAC cursor，投影固定类型化引用且不复制跨模块正文/路径。无Schema/依赖/外发变化；专项20、
  后端2844/3及wheel检查通过，Windows生产组合留A07。
- 2026-10-06 / `SUR-01-A05-A07`：新增失败关闭的Windows Survey组合；显式只读模式只挂四GET，写模式
  覆盖冻结十个定义Operation，默认/login-only继续关闭。首轮真实HTTP/PG在Version GET发现A06序列化边界
  错把Schema/ORM的零基`sequence_no`拒绝为503；按既有Schema合同修正为`>= 0`并增加回归断言，以全新
  隔离库完整重跑创建、读取、校验、原子送审/重放、Review批准和归档。无Schema/API/依赖/外发变化；
  Windows 11/PostgreSQL 18.6、定向46、后端2846/3及wheel检查通过。正式目标账户两份cursor key仪式、
  Server 2025、UI、Round/Response/Conclusion、Gate 3与发行继续开放。
- 2026-10-06 / `SUR-01-A06-A01`：核清Survey前端为零，Version完整投影可先建设严格只读问题卡片；
  TEMPLATE只作参考，实际面对面记录优先且任何来源说明都不自动成为客户事实。当前Handover/Capability
  row identity和MANUAL说明不足以让浏览器安全定位原文，决定先交付四读客户端/页面，再以独立兼容
  只读解析边界补齐按需定位，不猜UUID、不复制正文。本项纯文档，无运行行为变化。
- 2026-10-06 / `SUR-01-A06-A02`：新增未接页面的四读严格客户端；精确验证Envelope、父级身份、强ETag、
  两类品牌cursor、完整Version声明计数、零基问题/ordinal、V1规则和四类互斥来源。嵌套规则深冻结，
  不读取跨模块正文或路径。无后端/Schema/依赖/外发变化；定向25、前端79文件1420项、typecheck和
  production build通过，主JS 599.01 kB既有分块提示保留。
- 2026-10-06 / `SUR-01-A06-A03`：新增Survey列表/详情/Version问题卡片、项目入口及安全来源可用性提示；
  实际调研记录优先、TEMPLATE仅参考，MANUAL不冒充确认，Handover/Capability内部row ID不展示或猜路由。
  TEMPLATE仅导航受权Document历史，完整来源定位留A04。无后端/Schema/依赖/外发变化；定向27、前端
  81文件1429项、typecheck/build通过。静态路由使主JS增至625.76 kB，登记为发行性能后续项。
