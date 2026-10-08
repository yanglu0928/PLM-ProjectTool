# CR-PRT-005：Prototype Workflow 聚合资格与只读预览兼容扩展

日期：2026-10-08。状态：依 `CR-EXEC-001` 持续授权分步实施；Gate 2 原冻结提交 `64cdf09` 不改写。触发 WBS：`PRT-01-A11-A02`。

## 来源、冲突与风险

六阶段定义已将 `PROTOTYPE_SCOPE_DECISIONS`、`PROTOTYPE_COVERAGE` 设为 PROTOTYPE 阶段的两个必填项，数据库亦允许 PROTOTYPE→SOLUTION；运行 Registry、资格预览、Checklist 写入和阶段推进目前只开放至 REQUIREMENT。直接扩大 item_key 白名单会让缺失真实 Prototype Owner 的 PASS 失去事实依据。

现有资格预览把聚合版本引用命名为 `requirement_version_refs`，不能承载 Requirement 与 Prototype 两种受审主体。Prototype NOT_REQUIRED 决定固定受影响需求、reason、impact、`confirmed_by` 和可选 Review；现有冻结命令没有直接 EvidenceRef 字段。不得把 PM 的受权命令冒充客户签署，也不得把 Requirement 的来源 Evidence 说成决定自身的证据。Workflow 所需的依据必须分别来自：当前批准 Requirement 的固定来源 Evidence/Review、NOT_REQUIRED 决定及对应 Audit/可选 Review、以及需原型分支的 Approved PrototypeVersion/Review、受权固定制品与 Link/Coverage。

## 方案比较与选择

- 拒绝“只认有 Link/Version 的需求”：会把遗漏或未决定的需求从范围中静默删除。
- 拒绝“每条 NOT_REQUIRED 必须新造 Review/Evidence”：会伪造不存在的客户确认，且与既有 `DEC-20261008-1024` 的可选 Review 规则冲突。
- 采用当前批准 Requirement 完整集合为左侧权威范围，同一事务内把每条需求分到两类：由当前有效、固定版本的 NOT_REQUIRED 决定覆盖，或由至少一个当前 Approved PrototypeVersion 明确固定为需原型。交叉归属、缺项、外项目/过期版本、空范围均失败关闭。所有 NOT_REQUIRED 的情形仍逐条验证决定及 Requirement 的来源 Evidence/正式 Review，不等于跳过阶段。
- `PROTOTYPE_COVERAGE` 还要求需原型需求存在与当前批准 PrototypeVersion 精确双端绑定的 ACTIVE Link；仅 `VALIDATES`/`ACCEPTANCE_REFERENCE` 的已覆盖验收标准计入覆盖。所有当前验收标准必须由有效 Link 的覆盖并集覆盖，未被覆盖且仅有“原因”的项目不能自动 PASS，须通过独立受权例外/处理路径。制品当前可访问、Hash/固定版本、Review 和 Trace 均由后续 Owner 重证，不能由纯范围算法或前端提交替代。

## 与冻结基线的差异

Prototype 26 项 `/api/v1` Operation、请求/响应和 NOT_REQUIRED 既有历史不改。后续在已存在的、CR-WFL-008 新增的 `WORKFLOW_CHECKLIST_QUALIFICATION_GET` 上，对 PROTOTYPE 阶段增加只读、严格类型化 `qualified_subjects[]`（`subject_type`、`subject_id`、`subject_version_id`、`review_round_ref`），同时保留规范 Evidence UUID 集和 Workflow 强 ETag；Handover/Survey/Requirement 原响应保持不变。新投影不含正文、磁盘路径、指纹、客户身份详情或内部失败原因。Checklist 写请求不增加字段，写时仍重新完整复验；新增 PROTOTYPE→SOLUTION 运行白名单必须等两个真实 Owner、HTTP/PG 验收通过后才显式开启。该增量不是冻结 API 的 Breaking Change，新增投影仍按可追溯变更处理。

## 实施、验证、迁移与回滚

1. A02 先实现纯范围策略和正反例，输入只代表候选事实，不能生成 Workflow PASS。
2. A03 构建跨模块公开证明 Port 与 Prototype Owner，锁定当前 Requirement 范围并重证决定、Review、Evidence、Artifact、Link、Trace；缺证明统一失败关闭。
3. A04 接入 Registry/预览/Checklist/Stage Transition，保证旧阶段响应与行为兼容、权限不扩大、原操作幂等与强 ETag 不变。
4. A05 做 Windows 11/PG18.6 真正的包含/遗漏/冲突/漂移/全 NOT_REQUIRED/部分覆盖/跨项目/撤权与顺序推进验证，完整后端/前端回归、开发 wheel 和 Secret 扫描；Server 2025 单独实机验证，Debian 13 按用户指令跳过。

当前选择不增加 Schema、依赖或数据迁移；若 A03 证明既有不可变数据无法承载完整规则，须先补充本 CR 的数据差异和 up/down/历史迁移方案，不能在代码里伪造或补写旧决定。应用回滚可停止新增 Registry/Router 注册，现有 Requirement/Prototype/Workflow/Audit 历史保留；一旦已有 PROTOTYPE Checklist/Transition 历史，不得删除记录或把 Workflow 实例自动降回旧定义。Gate 3、UAT 和可用包结论仍只按客观证据关闭。

## 2026-10-08 A03 兼容修订：受审主体的 Evidence 归属

P01/P02 后发现通用 `ChecklistQualificationSubject` 要求每个受审主体至少一个 EvidenceRef，但 `PRT-03` Approved PrototypeVersion 的正式依据是固定 DocumentVersion 制品、Review 和 Trace，而不是其自身 EvidenceRef。把 Requirement 来源 Evidence 复制到 PRT-03 主体会错误陈述证据归属；虚构 Evidence 更不可接受。选择允许聚合中的单个主体 Evidence 集为空，但聚合整体仍必须至少包含一个经证明的 Evidence；本阶段 Requirement 主体须继续提供其真实来源 Evidence，PRT-03 主体以真实 Review 与受权制品/Trace 由 Owner 另行证明。现有 Handover/Survey/Requirement Owner 输出不变，单主体 `CurrentChecklistQualification` 的非空 Evidence 约束不改。空 Evidence 的 PRT-03 不会凭此获得 PASS，A03 Owner、A04写时复验与A05实例测试仍是必需前置。

差异/风险：通用聚合 Subject 构造约束小幅放宽，若错误 Owner 输出全部无 Evidence 可能削弱登记依据；在 Aggregate 根约束新增总 Evidence 非空，并保持受权 Registry、聚合写时原样匹配和 Review Basis 持久化。无 Schema、API、权限或数据迁移。验证计划：零 Evidence 聚合拒绝、混合主体的 Evidence/Review 身份和排序、既有 Workflow 全量回归，后续真实 PG/HTTP。回滚：A04 尚未开放 Prototype 注册前可撤销该内部 DTO 兼容扩展；开放并形成 Checklist 历史后不得删除记录，应先停止新注册并制定保留历史的迁移方案。

## 2026-10-08 A03 兼容修订：Document 制品物理完整性

P02 复核发现既有 `PrototypeVersionCurrentValidator` 的 Document Proof 只锁数据库中的 AVAILABLE/Hash/固定Version元数据，不能单独证明本地文件仍在或实际字节匹配。若直接把该元数据当作“制品当前可访问且Hash正确”的 Workflow PASS，会高估资格。A03 新增 Document 所有者公开物理校验 Port：在同一项目事务重读固定Version/FileObject当前状态与元数据，并用既有本地存储安全校验逐字节验证 SHA-256、长度、文件身份/重解析点；仅返回不含路径的证明。Prototype Owner 必须逐个消费；缺失、篡改、超限失败关闭。无 Schema/API/生产依赖；可能增加预览/Checklist 的磁盘读取成本，A05 需测延迟与并发，不得以缓存元数据替代实际校验。回滚仍须保持 Prototype Registry 关闭，不可静默绕过物理证明。

## 2026-10-08 A05 兼容修订：PostgreSQL 时区化 Audit 证明

A05 隔离 Windows11/PG18.6 实测发现：`timestamptz` 的 `decided_at` 由驱动以本机会话时区 `Asia/Shanghai` 返回，而 Audit 证明适配器要求输入对象 `utcoffset()==0`，导致已存在且有效的同项目/用户/动作 Audit 被误判缺失，Prototype资格返回409。旧单元测试仅使用UTC夹具，未覆盖真实PG返回形态。拒绝通过跳过Audit检查或修改数据库全局时区解决：前者削弱事实证明，后者改变部署环境。选择在Audit所有者公开适配器边界只接受有时区的时间戳，将输入和读回Audit时间规范化为UTC后按相同绝对时刻、唯一事件及五分钟窗口验证；无时区、缺失、重复、过迟仍拒绝。差异仅为内部时间表示，不修改冻结API、Schema、权限或业务规则。风险是时区转换边界误差；增加UTC+8真实形态、naive拒绝、唯一/过迟负例及隔离PG/HTTP回归。回滚须保持Prototype生产注册关闭；不能回滚为跳过Audit。原冻结提交与既有业务历史不改。

## 2026-10-08 A05-P04 性能偏差：同项目20并发资格读取

Windows11隔离PG18.6/pgvector、真实Approved Prototype/Review/Trace/Link和本地文件字节校验的首次ASGI内进程预检中，两项资格各同时发出20个GET，40个请求均200且ETag/阶段正确，但`PROTOTYPE_SCOPE_DECISIONS`近秩P95约1836.93ms、`PROTOTYPE_COVERAGE`约1559.01ms，均高于初始非AI GET P95≤500ms目标。样本为同一Project/一份小合成文件，含应用与数据库但无Uvicorn网络、目标服务账户或正式信任源；既不能据此断言发行环境SLA失败，也不能把功能正确描述为性能PASS。单次P95样本少且可能混有连接预热成本，需重复测量。

候选原因包括默认连接池5+10的排队/建连、共享ProjectRow与各Owner只读锁、跨模块多轮SQL、线程调度及文件完整性重算。拒绝直接提高SLA、关闭磁盘字节校验或跳过Review/Audit/项目隔离。先加入只读计时/连接池诊断，重复本机样本并与真实Uvicorn loopback区分；若定位为生产实现瓶颈，另记录所选最小优化、兼容/安全影响、回滚与单/20并发回归后实施。暂不改生产连接池或资格规则。生产Prototype入口继续关闭，A05/Gate3不得标PASS。

同日复测在每项预热后做三轮20并发：默认池`PROTOTYPE_SCOPE_DECISIONS`三轮P95中位1618.71ms、`PROTOTYPE_COVERAGE`1557.25ms；另一轮分别1538.68/1555.31ms。20并发`/health/live`对照P95中位0.70ms，排除ASGI测试链路本身为主要瓶颈。同一测试库仅将诊断运行时池临时改为20+0（不改生产默认）后，默认池1531.58/1560.53ms对比扩大池958.93/1001.37ms，说明连接池容量是部分原因但不足以达500ms。仍需定位查询/锁/物理校验成本及真实网络服务表现；不得将该诊断当作生产参数建议或性能通过。诊断运行时结束即dispose，原功能路径和正式配置未变。

## 2026-10-08 A05-P04-P02 性能修订候选：资格预览项目授权共享锁

复核发现上轮20+0实验仍让外层Session校验走默认池；把Session与资格事务都指向同一20+0诊断池后，两项P95仍约933/889ms。SQL事件计时在每池各122次资格请求（含预热）观察到9394条语句；其中同一Project/Member/Department授权SELECT执行122次，默认池累计等待约96秒中的约88秒，单次最长约1.4秒。静态核对确认资格预览错误复用了写命令`WORKFLOW_CHECKLIST_RECORD`策略；该策略必需`FOR UPDATE`锁，预览的长事务持有同项目排他行锁，20个只读预览互相串行。会话/Review/Artifact/Trace证明不可为了加速跳过。

所选最小修订：新增只用于资格预览的`WORKFLOW_CHECKLIST_PREVIEW`项目授权策略，角色仍仅PROJECT_MANAGER，仍在同一个资格事务中锁Project/Member/Department三行，但使用PostgreSQL `FOR SHARE`，从而允许同项目只读预览共享锁，同时与撤权/归档/成员更新的`FOR UPDATE`保持冲突。Checklist写命令继续使用原`WORKFLOW_CHECKLIST_RECORD`及排他锁；不改其他读策略、公开API、Scope或授权范围。风险是共享锁与写锁转换、撤权等待及事务漂移边界，须以隔离PG并发预览/撤权、权限拒绝、写时重新证明、全量授权/Workflow回归验证；不得只凭P95改善放行。无Schema、数据或配置迁移；如验证失败，生产Prototype入口继续关闭，回滚新预览策略并恢复旧排他锁，历史数据不变。若目标仍不达500ms，再独立定位SQL数量/连接池/物理证明，不降低验收阈值。

实施与复验：新预览策略还显式拒绝ARCHIVED，保持旧写策略的归档边界；真实SQL为`FOR SHARE OF prj_projects, prj_project_members, prj_departments`。隔离PG两笔并行预览事务可共存，同一成员撤权UPDATE在持锁期间触发预期lock_timeout；原写策略仍`FOR UPDATE`。仪表化预检中该授权语句122次合计约1.1秒（旧排他锁约88秒），说明主要串行点被移除。关闭SQL事件计时后的三轮20并发P95中位：默认池约752.69/748.22ms，全链路诊断20+0池约696.74/683.13ms；均仍高于500ms，因此性能状态仍FAIL，生产入口继续关闭。后端3245通过/3跳过/4795子例、旧全NOT_REQUIRED隔离PG/HTTP回归通过；后续仍须补Uvicorn loopback、跨线程撤权后的资格拒绝和剩余SQL/文件成本分析。不能以本机共享锁改善替代发行验收。

P04-P03已补真实Uvicorn loopback：同一隔离Windows11/PG18.6实例、同一授权及20并发/三轮，在不读取系统代理的测试客户端下，`PROTOTYPE_SCOPE_DECISIONS` P95中位710.31ms、`PROTOTYPE_COVERAGE`714.07ms，全部返回200/强ETag/阶段正确；健康端点对照约83.28ms。首次客户端使用默认环境代理导致空502，非应用响应，隔离工具改`trust_env=False`后复验通过；不改生产代理配置。撤权后资格与写命令404、无Checklist历史的既有PG/HTTP隔离用例重跑通过。网络链仍未达500ms，不开放生产Prototype入口；每请求约77条SQL和文件证明成本仍需独立优化，不能把Uvicorn实测描述为正式发行SLA。

## 2026-10-08 A05-P04-P04 候选优化：消除Requirement完整范围重复扫描

同一Prototype资格事务中，Prototype Owner先调用Requirement仓储`lock_complete_scope`，随后Requirement Owner的`qualify_only_current_in_transaction`又调用相同仓储重扫一次；SQL诊断中多个Requirement子表查询每请求出现两次。拒绝跨请求缓存或跳过当前版本、证据、Review证明。选择由Requirement Owner新增内部组合方法，在自身同一事务内**一次**获取完整锁定范围并完成原资格证明，同时返回`(locked_scope, qualification)`给Prototype Owner；原Requirement独立资格接口仍调用此方法但仅返回证明，保持外部行为与失败关闭不变。Prototype Owner不再持有单独的Requirement仓储依赖，不能接受调用方提供的未验证范围。风险为返回范围与证明身份错配、异常映射或锁生命周期变化；验证须包括单元正反例、SQL计数减少、隔离PG真实Owner/HTTP的缺Link/文件漂移/跨项目/撤权/多原型及20并发、后端全量回归。无Schema/API/权限/数据迁移；回滚恢复原两次扫描，历史不变，生产入口在性能和安全证据齐全前继续关闭。

实施复验：Requirement Owner内部新增一次扫描的组合返回，独立Requirement调用行为不变，Prototype Owner仅消费该Owner返回的锁和资格且仍核对Project/Item/Subject/Version。SQL诊断相同122次请求由9394降至7686条（每请求约77→63）；Windows11隔离PG18.6真实Uvicorn loopback、三轮20并发、无SQL计时器的两项P95中位约594.00/632.23ms，均仍高于500ms，不能标性能PASS。混合范围缺决定/文件漂移/双重认领、部分Coverage、ILLUSTRATES、跨项目、撤权与多原型并集的隔离PG/HTTP负例顺序回归退出0；后端3246通过/3跳过/4795子例。生产入口继续关闭。下一步可分析仍存在的约63条SQL/请求及文件证明时间，不以降低强证明或放宽阈值代替优化。

P04-P05仅在隔离验证工具中包装真实`LocalFileStorage.verify_content`测时，不缓存或跳过字节校验。122次网络资格请求的文件证明P95约10.49ms、总耗时约632.40ms，同轮Uvicorn两项P95约618.01/616.35ms；文件证明不是网络P95超500ms的主因。同一工具的ASGI内进程并发文件P95在约50/72ms，显示线程调度/主机负载影响，不应以单轮差异推断文件系统性能。仍需分析约63条SQL及Review/来源证明的多轮查询，任何合并必须保留同事务锁与完整一致性验证。此轮无生产代码/Schema/API/配置修改，性能状态继续FAIL。

P04-P06仅扩展隔离SQL诊断，按语句首个`FROM plm.<table>`表前缀粗分，同一122次请求共7686条：`rvw`2196（18/请求）、`req`1952（16/请求）、`prt`1708（14/请求），三者合计5856（约76.2%）；其余`evd`610、`prj`366、`auth/wfl/doc`各244、`cap`122。分类不是精确Owner调用图；并发语句耗时求和也不是端到端墙钟耗时。静态复核Review `get_round`需验证Review根、所有Round、目标Round及六类子表；本夹具Requirement和Prototype各一轮，约18条Review查询/请求与计数一致。禁止为了减查询删除Reviewer/Decision/Event/SnapshotRef/SubjectLock一致性验证、跨事务缓存已批准结果或放宽500ms目标。下一独立P07先设计同事务安全批量读取、锁序/类型转换/失败关闭验证，确认可行后再实施；若无安全收益则维持性能FAIL并转不依赖项。当前没有生产代码、Schema、API或配置变化。

P04-P07按前述方案仅做隔离探针，保持根/轮行锁及正式仓储不变：同一已批准Review轮次的六类子表顺序查询和psycopg pipeline在同一PG事务中逐表返回相等，完整Workflow链通过。60轮单连接P50顺序0.336ms/pipeline0.262ms；20独立连接三轮近秩P95中位顺序13.029ms/pipeline16.095ms。无稳定并发收益，且探针不包含SQLAlchemy共享事务/锁序/篡改拒绝的生产等价证明。按DEC-1080不实施Review生产更改，避免高风险低收益；无兼容或迁移影响，可撤探针回滚。剩余Requirement/Prototype查询另起单一任务分析，不将探针退出0解释为P95目标达标。生产入口关闭、Gate3阻塞状态不变。

P04-P08前置核查找到唯一候选：Requirement快照仓储已取回并共享锁定验收标准行，但快照DTO仅保留文字，Prototype又经Requirement公开证明Port对每个当前批准版本重读根/版本和验收行以取得稳定ID。不能删第二次读取，因为它额外证明根ACTIVE、指针当前、版本APPROVED、Review引用及行数/序号/ID；不能从文字生成ID。候选方案是由Requirement Owner在同事务内提供经过上述相同校验的稳定ID，同时沿用共享项目/版本/验收行锁及原Port合同。风险为混淆快照与当前指针、改变共享DTO或篡改拒绝。实施前需明确内部结构差异和回滚，随后做正反例、SQL计数、全量后端和真实PG/HTTP 20并发；现阶段仅记录候选，没有生产改动或性能结论，不开放Prototype入口。

## 2026-10-08 P04-P08-P02 所选内部优化：已锁定快照附带稳定引用证明

来源/冲突：P04-P08发现每个当前批准Requirement的验收标准行已由`lock_snapshot`共享锁定并校验连续序号，但`RequirementVersionValidationSnapshot`只有文字草稿；Prototype为获取稳定ID再走Requirement `prove_current_acceptance_refs`的根/版本JOIN和行读取。方案A直接删除第二次证明不接受，会丢失ID及当前批准条件；方案B把ID加到公开/共享ValidationSnapshot不接受，会扩大通用快照DTO及序列化/测试范围；选择方案C在Requirement快照仓储新增内部“快照+ID”同源返回，Requirement Workflow锁携带仅本链消费的可选`RequirementAcceptanceRefsProof`。原`lock_snapshot`与原独立Proof Port均保持可用；未携带时Prototype保留旧证明路径。

等价性：项目共享锁先防新增/改根；所有Requirement根和版本仍按原次序共享锁定并要求根ACTIVE、当前指针等于最新APPROVED版本、Review双引用有效；同一快照仓储对验收标准行仍`FOR SHARE`，其连续序号、数量、ID有效性/唯一性在构造Proof时检查。Requirement Owner先用原`current_issues`与Review/Evidence证明该快照有效，再交给Prototype；Prototype再次校验Proof的Project/Requirement/Version和ID数量。正式API/Schema/权限/业务规则/Hash不变。风险为Proof与快照错配、可选旧路径造成分支差异、事务边界变化；用单元负例、真实PG篡改/撤权/跨项目和SQL计数验，原锁序不变。

迁移/回滚：无数据迁移或配置升级；只部署同步代码。若任一等价性或回归失败，保持Prototype生产开关关闭并恢复Prototype始终调用独立Proof Port，丢弃内部侧带Proof；历史和冻结提交不改。即使查询数下降，也必须重新跑真实Uvicorn 20并发P95≤500ms才可宣称性能通过；Server2025/正式信任/发行仍独立验收。本节为实施前计划，以下验证结果待执行后补。

实施后复验：旧`lock_snapshot`和独立Proof Port均保留；新同源内部返回只从已共享锁定的验收行构造ID，内部Workflow锁校验Proof的项目/需求/版本/数量，缺Proof时Prototype仍读旧Port。Windows11隔离PG18.6的122次资格读取，Requirement首FROM由1952减至1708（每请求16→14），总查询7686→7442（63→61/请求）。新增正反例及全量后端pytest3250通过/3跳过/4795子测试通过；跨项目/撤权、混合范围/文件损坏/双重认领的真实PG/HTTP回归退出0。真实Uvicorn20并发P95约593.788/596.738ms，仍超500ms；本改动仅证明查询减少和既定负例保持，不是性能PASS、生产入口或Gate3放行。无迁移，原回滚路径保持。

## 2026-10-08 P04-P09 候选修订：Requirement同事务Evidence证明复用

来源/证据：P08后隔离SQL诊断122次资格读取仍有7442条，其中`evd_evidence_records`一类语句488次（4/请求），单连接池累计约2.6秒（SQL事件计时环境，不可除成网络P95）。静态核对发现Requirement当前性验证对来源Evidence/能力评估Evidence分别调用Owner Proof，随后Workflow Owner又为Checklist证据调用相同Evidence Proof；本夹具可重复读取同一项目Evidence。所有Proof由Evidence Owner在同一资格事务中读取ELIGIBLE行并`FOR SHARE`，没有授权跨请求复用的依据。

方案比较：A 跨请求缓存拒绝，会让撤权/失效及文件状态漂移漏检；B 删除Checklist再证明而不传Proof拒绝，会失去DocumentId/VersionId、锁版本、指纹完整检查；C 选择在Requirement Validator**单次当前性检查内部**按EvidenceId收集并复用已锁定的原始Evidence Owner Proof，仅在该次调用完成且无Issue后交给Workflow Owner；Owner仍用原严格字段/项目/ID检查构造Checklist证据，未出现在该集合的Decision Evidence仍走原Proof Port。源证明和能力证明各自原有规则不变，整个集合不进入跨请求/事务缓存。

差异/风险：新增内部Validator组合返回和事务内缓存；通用`current_issues`对外返回及业务规则不变，内部同EvidenceId多次读取缩为一次。若被篡改Proof字段、缺失、错误项目、重用旧Snapshot或未验证集合会被错误接受，则必须失败关闭；单元覆盖这些负例并以跨项目/撤权/损坏文件真实PG/HTTP回归、SQL计数和全量后端验证。无Schema/API/权限/依赖/数据迁移；保持Prototype生产入口关闭。可恢复旧每次Proof调用与旧Workflow Owner再读，历史不动。只有真实Uvicorn20并发P95≤500ms且相关Gate证据齐备，才可考虑放行。本节为实施前计划。

实施后复验：Validator按单次调用内EvidenceId复用，存在Issue时不给Workflow Owner Proof；Owner继续严格检查项目、ID、DocumentId/VersionId、锁版本和指纹，未包含的Decision Evidence从原Port读取。122次资格GET，SQL总数7442→7076（61→58/请求），`evd`首FROM610→244，`evd_evidence_records`模板488→122。全量后端pytest3253通过/3跳过/4795子测试通过；跨项目/撤权、混合范围/文件损坏/双重认领隔离PG/HTTP回归退出0。真实Uvicorn20并发P95约584.504/575.858ms，仍大于500ms；单轮差异不可归因或称性能PASS。无迁移，既定回滚路径及关闭入口保持。

P04-P10只增加隔离验证工具的临时阶段计时，不改生产池或业务规则。测试运行时默认池5+10与临时20+0池的ASGI20并发P95约645/637对550/553ms，扩大池部分改善但未达目标；真实Uvicorn三次阶段诊断仍约565–598ms。第三次资格预览服务方法P95约87ms、Prototype Owner约77ms，预览峰值重叠5，与端到端约574–580ms差距显著。方法计时包含线程/数据库等待且是嵌套区间；健康端点对照约91ms，不能从业务响应直接扣减。尚不能区分服务接入、线程排队、连接取得和本机loopback客户端成本，不选择生产连接池或安全证明的更改。下一项只在隔离工具中校准客户端/ASGI入口/线程执行/响应完成时间线；性能继续FAIL，入口关闭。

P04-P11用不含凭据的合成探针ID测四时点；真实Uvicorn loopback第二次20并发的业务进入ASGI前P95约502/487ms，ASGI内约87/99ms，响应发出后到客户端完成约72/76ms；健康对照前段约117ms、ASGI内约0.45ms。业务端到端约564/575ms，仍FAIL。阶段P95不可相加，且当前客户端/服务器在同一Python进程中；大前段可能反映客户端与Uvicorn竞争GIL/调度、连接生命周期或服务端接入压力，不能直接判定生产根因。下一独立P12改用独立客户端进程重复同安全断言与负载，先验证测量方法，再考虑生产调参。无生产变更/迁移，入口保持关闭。

P04-P12改用独立httpx客户端子进程，同样20并发、健康对照、强ETag/阶段断言，合成Cookie仅经标准输入传递。父/子`perf_counter`现场区间校准通过，两个独立进程运行的业务P95约651/655及652/644ms，健康约68/64ms；第一轮业务ASGI内P95约561–587ms，第二轮Prototype范围预览服务P95约519ms、峰值并行20，Owner约423ms。P11同进程“ASGI前占主导”的定位被独立进程对照推翻；不能依前者修改Uvicorn接入。服务端并发争用是真实本机候选，但连接池/线程/CPU贡献仍待隔离。只新增验证工具，无生产变更/迁移；性能继续FAIL、入口关闭。

P04-P13在同一隔离库/文件、独立客户端20并发下，对照临时20+0池与原默认5+10池；测试顺序为20池先、默认池后。两项P95约517.557/541.791ms对655.439/672.851ms，说明扩大连接容量可在该本机夹具显著改善，却仍未满足500ms。未单独测连接Checkout等待，也没有交错顺序的稳定统计，不能据本轮直接改生产参数或宣称完整根因；后续须在20池下定位剩余成本并复验负例/目标环境。无生产配置、Schema、API或数据迁移变化，Prototype入口继续关闭。

P04-P14补充默认→临时20+0→默认交错两轮独立客户端测量，并仅在临时池记录Owner阶段/SQL/文件成本，细节见`docs/progress/prt-01-a11-a05-p04-p14-interleaved-owner-sql-file.md`。两轮临时池两项P95约584/568及651/557ms，均未同时达到500ms；第二轮首项相对默认前段645ms无稳定收益。第二轮122次资格请求有7076条SQL（58/请求），SQL执行求和约47.83秒，文件证明P95约70.84ms，Prototype Owner/Requirement Owner P95约529/254ms。嵌套/并发区间不可相加，且计时器对被测池有扰动；本轮不采用生产池变更、不削弱安全证明。偏差/风险仍是性能FAIL；P15仅先核对安全可合并的重复查询。无生产迁移或配置升级，撤诊断工具可回滚，入口与Gate3继续关闭。

P04-P15静态核查Owner/Review58条SQL：P04-P04范围复用、P08-P02验收引用复用、P09 Evidence复用已消除明确重复；Review全轮次读取与目标Round单独共享锁不可直接合并，六类子表互不重复且用于失败关闭的一致性证明。未证实安全可删查询，故不改生产代码、不虚报性能改善。下一步仅在隔离工具中测连接Checkout等待及SQL模板分布；无生产迁移/回滚动作，维持性能FAIL与入口关闭。见P15进展和DEC-1088。

P04-P16在临时20+0池的独立客户端负载上加隔离连接取得路径及无参数SQL指纹/模块标签探针；两轮122次资格GET各7076条SQL，连接路径244次P95约9.38/11.19ms，业务两项P95约598/564及574/589ms，均未同时达500ms。连接路径包含可能的预检/新建，不是纯排队；第二轮按SQL累计耗时前八模板七个属Review、一属Project，不能以此直接删锁/校验。P17仅设计安全共享事务批量读取可能性，未证明前不修改生产。无生产配置/API/Schema/迁移，撤诊断探针可回滚；性能FAIL、Prototype入口及Gate3关闭。见P16进展和DEC-1089。

## 2026-10-08 P04-P17候选修订：Review六类子表单查询读取

来源/冲突：P16前八SQL耗时模板七属Review，P15已确认Review根/全部轮次和目标轮共享锁不可删，P07 pipeline无并发收益。新候选仅将目标轮锁定**之后**的Assignment/Decision/Snapshot/SnapshotRef/SubjectLock/Event六类只读子表按原过滤与排序以单条`UNION ALL`/JSONB取回，保留根/目标轮锁和原全部一致性校验。隔离探针两轮同事务行内容相等，20连接三轮近秩P95中位顺序约17.785/15.356ms、合并约4.966/5.558ms，但只是微基准，不证明生产收益。

实施前差异/风险：SQLAlchemy行映射将变成JSONB载荷，必须严格还原UUID、bytea、UTC timestamptz、整数、可空字段和逐表顺序；任何漏行、重复、错scope/project/round、恶意事件/快照/锁篡改必须仍失败关闭。原`get_round` DTO、权限、错误语义和锁序不变；不得跨事务缓存或绕过字节/Review证明。无Schema/API/权限/依赖/数据迁移。P18先定向/真实PG篡改负例及完整后端回归，再独立客户端20并发复验；若等价性或性能不稳定，恢复六查询路径，历史不改。Prototype入口/Gate3保持关闭，性能继续FAIL。本节是生产编码前计划，实施结果待P18客观记录。

P04-P18实施后：仅目标轮已锁定后的六类只读子表合并为一条绑定参数查询，严格按ORM字段/类型还原并核对集合、轮次与主键；原根/轮共享锁、全部轮次计数与六类事件/快照/受审锁一致性校验保留。定向11/33子例、后端3256通过/3跳过/4806子例；隔离PG以仅该临时库的replica事务注入错误Decision事件Actor，读取拒绝且恢复后正常，混合/隔离/多原型PG/HTTP均退出0。122次资格GET SQL由7076降至5856（58→48/请求）。独立客户端20并发临时20池两轮两项P95约533/533及540/512ms，仍未同时≤500ms；默认池约614–673/604–634ms。性能FAIL、默认生产池与关闭入口继续保留；无Schema/API/权限/依赖/配置或数据迁移，恢复六查询路径即可回滚。GLOBAL真实Review和非合成规模仍待验证，见P18进展与DEC-1091。

P04-P19补证同一共享仓储在真实PG合成GLOBAL批准双评审及撤回轮次下正确还原`project_id=NULL`，原GLOBAL/Audit与PROJECT链退出0。三轮默认→临时20+0→默认独立客户端负载，临时池两项P95约480/492、476/486、511/486ms，第三轮首项仍超500ms；默认池连接取得路径P95约133/144/134ms、临时20池约9.7/10.3/9.6ms，路径含预检/新建，不能称纯排队。P20仅在目标PG/Worker资源预算与可回滚配置设计后考虑生产池调整；当前不改配置、不标性能PASS，入口/Gate3继续关闭。无Schema/API/权限/数据迁移，诊断可撤，详见P19进展与DEC-1092。

P04-P20前置预算：本机一次性PG18.6为100个最大连接/3个超管保留；生产Windows API一Worker，当前业务池上限15、独立维护准入池20，三个Worker各业务4+准入1，静态合计上限50。候选API业务池20+0使该合计55，相对本机临时库非保留额度97留42，但目标Server PG设置、其他连接消费者与动态内存占用未知，不能据静态算式认定安全。Server 2025 VM配置16GiB/16vCPU且当前关闭，宿主可用内存低于VM标称；本项不启动VM、不改生产配置。P21仅先实现显式受控配置与启动预算负例，默认保持5+10、入口关闭；目标实机和重复P95证据齐全前不升级为发行参数。无迁移，撤可选配置应回到原池并保留历史；详见P20进展与DEC-1093。
