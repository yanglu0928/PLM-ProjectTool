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
