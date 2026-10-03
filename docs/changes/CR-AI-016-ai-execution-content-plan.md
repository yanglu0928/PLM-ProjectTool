# CR-AI-016：AI 执行内容必须绑定不可变 Content Plan

日期：2026-10-03；状态：依 V1.1 持续授权登记，分片实施中；关联 Gate 2 冻结提交 `64cdf09`、DM-04、API-03、CR-AI-015、Schema0064/0068～0071。WBS `AI-04-A06-P03-P02～P04`。

## 冲突与证据

冻结合同要求 `AITask` 固定不可变输入版本，每次 `AIInvocation` 保存实际发送的 Input/Context 版本和载荷摘要；Prompt、Input、Context 或 source version 变化时不能伪装成确定性重放。现有实现只在 Task/Egress Preview 中固定 `DocumentVersion`，而 Document Owner 读取解析正文必须同时提供唯一 `ParseRecord`。同一 `DocumentVersion` 可以因 parser profile/version 或重试产生多个成功解析结果，因此 Worker 运行时选择“最新成功解析”不能唯一复现批准时正文。

当前 `EgressPreviewService` 还接受客户端提交 `payload_fingerprint`，并把 `source_refs_fingerprint` 直接计算为业务 InputRef 集合摘要；Task 创建继续要求该摘要等于 Task InputRef 摘要。这一结构没有位置保存 `ParseRecord`、ParseResultRef/hash、正文编码策略、模板渲染版本或 Token estimator 身份。发送原文件字节会改变 `minimum.document.text.v1` 的语义，也不能替代解析文本批准。

仓库尚无 `rag` 模块、`RetrievalRun` 或 `ContextBundle` 生产实现。已有 Task Policy 可引用 RAG/context policy，但执行器不能把未实现的 policy 静默解释为“无 Context”。Prompt 正文和最小参数已经存在于各自 Owner 数据中，但当前 Grant 仅投影哈希；Envelope 构建器不能直接跨模块查表或从哈希猜正文。

## 方案比较与决定

- A：执行时选择最新成功 ParseRecord。否决；解析结果改变会使已批准载荷漂移，并破坏重试确定性。
- B：把原始 Document 文件作为 Provider 输入。否决；与已批准的最小文档文本策略不等价，并扩大外发类型与载荷。
- C：把 ParseRecord 当成公开 AITask 输入，替换现有 DocumentVersion。否决；会把文档模块内部处理身份泄露为业务输入，并对冻结 `/api/v1` 形成不必要破坏。
- D：Preview 阶段由服务端解析业务 InputRef，建立独立、不可变的 `AIExecutionContentPlan`，固定精确内容来源、渲染/编码/估算策略；Authorization 和 Task 只引用并复核该 Plan。选择 D。

## 目标模型与边界

1. `AITaskInputRef` 继续表示用户选择的业务输入版本；不得由 ParseRecord 替代。
2. `AIExecutionContentPlan` 是 AI Owner 的不可变执行快照，至少固定：Project/Scope、按序 InputRef、每项 Owner 内容来源身份、PromptVersion、参数摘要、context policy、正文最小化策略、Envelope 编码版本、Token estimator ref/version 和整体 fingerprint。
3. Document 内容来源必须由 Document Owner 投影并包含精确 `DocumentVersion`、`ParseRecord`、ParseResultRef、Parser profile/version、源文件 hash、结果 hash 和受权内容读取证明。AI 模块不得直读 Document 表或 storage locator。
4. Prompt 内容由 Prompt Owner 按 Grant 中的精确 template/version/hash 投影；任务参数由 AI Task Owner 按已持久化摘要投影。内容只存在于短生命周期内存对象，不进入 Job、Outbox、Audit、普通日志或异常。
5. RAG policy 只有在受权 `RetrievalRun`/不可变 `ContextBundle` 实现并进入 Plan 后才可执行；明确版本化的无检索策略可生成空 Context。未知、未实现或需要 RAG 的 policy 失败关闭。
6. Egress Preview 的不可变 source refs 仍展示业务 DocumentVersion，另外以安全摘要标识 Content Plan；浏览器不接收解析正文。AI_TASK 的最终 payload fingerprint 必须由服务端同一 Envelope 构建器计算，不接受客户端自报值作为放行依据。
7. Task 创建必须绑定授权对应的 Content Plan；每次 Invocation 再读取同一 Plan、重建 Envelope，并逐字节核对 fingerprint、字节/Token/记录上限和当前授权。Plan 或来源变化必须新建 Preview/Authorization/Task。

## 实施顺序

1. `P03-P02-A01`：定义无正文 Content Plan、内容来源身份和 Owner Port 合同，覆盖严格校验与规范化 fingerprint。
2. `P03-P02-A02`：实现 Prompt/Task 参数内容 Owner 与严格、无动态执行能力的模板渲染器。
3. `P03-P02-A03`：实现 Document 解析内容 Owner，以精确 ParseRecord/结果 hash 读取并前后复核，完成 Windows 11/PG18.6/本地文件正负链。
4. `P03-P02-A04`：实现 provider-neutral Envelope 规范编码和可注入、版本化 Token estimator；只接受明确支持的 context policy，不执行网络 I/O。
5. `P04`：以增量 Schema（编号在实现切片分配）持久化 Content Plan 及来源行，重构 AI_TASK Preview/Authorization/Task 绑定；非 AI operation 保持原合同。此切片再更新 ORM、Migration、API 文档和兼容测试。

## P03-P02-A01 实施结果

已新增不含正文的 `AIExecutionContentPlan`、精确内容来源身份、Prompt/Context身份、规范化fingerprint、Grant逐项匹配以及 `AIExecutionContentIdentityOwnerPort`。Plan显式固定Envelope编码和Token estimator版本；Context只允许完整NONE或RAG_CONTEXT形态，未知语义仍留给后续策略注册表失败关闭。定向10项、后端2173运行/3跳过和开发wheel通过；无Schema/API/依赖/运行装配/外发。开发期括号、parser version规则和测试断言边界问题均修复后完整重跑。A02继续实现Prompt/Task参数短生命周期Owner和严格渲染器。

P03-P02-A02已实现AI-owned Prompt/Task参数短生命周期投影和 `strict-placeholders.v1`：只允许input/context/parameters三个字面占位符，动态文本统一NFC/LF/UTF-8且不二次展开。PostgreSQL Owner锁定精确QUEUED Task、当前活动Prompt并复核JSONB参数摘要。Win11/PG18.6真实Grant→内容→渲染链及Prompt/参数漂移拒绝、定向16、后端2179运行/3跳过和wheel通过；无Schema/API/依赖/Invocation/外发。旧Prompt若不满足新占位符语法不可执行，只能创建并准入新版本。A03继续Document精确ParseRecord内容Owner。

P03-P02-A03已实现Document-owned精确解析内容Owner、PostgreSQL五行当前事实锁、私有ParseResult存储复核和AI反腐层。规划阶段按确定顺序选择一个成功ParseRecord，执行阶段只读取Plan冻结的ParseRecord/ParseResultRef/hash；正文最小投影删除locator/confidence并规范为NFC/LF/UTF-8。后台执行新增内部 `AI_TASK_EXECUTE` 策略，以Task原请求人当前Project权限重新鉴权，不复用浏览器Session。Win11/PG18.6/本地文件证明新解析结果出现后旧Plan仍读取旧结果，暂停成员和文件篡改均拒绝；定向19、后端2185运行/3跳过、wheel通过，Invocation=0。无Schema/API/依赖/外发。A04继续Envelope/Context/Estimator。

P03-P02-A04已实现 `provider-neutral-json.v1` 规范Envelope、显式Context Policy Registry和可注入版本化Token Estimator。编码前补强Plan来源身份，ParseResult原始hash之外增加最小 `projection_fingerprint`，由Document Owner规划/执行两次计算并由Envelope复核。当前仅 `no-retrieval.v1/NONE` 可构建；`project-documents.v1` 等RAG policy因无RetrievalRun/ContextBundle Owner继续失败关闭。Win11/Python3.13在socket禁用时确定性构建、服务端payload证明与限额负例PASS；A02/A03 PG链重跑、定向24、后端2191运行/3跳过、wheel通过。无Schema/API/依赖/Invocation/外发。P04继续持久化Plan与服务端Preview绑定。

P04-P01前置核查确认现有Preview早于Task且不含task type/Prompt/参数，不能在不改变AI_TASK请求语义的情况下批准完整Envelope。选择AI_TASK Preview新增精确 `ai_task_plan`，由服务端计算record count/payload fingerprint；旧客户端自报字段在AI_TASK模式不再接受，非AI operation不变。Schema0072拟新增Plan/Source并把Authorization/Task/Snapshot/Invocation绑定同一PlanRef；旧NULL历史只读、可撤销但不可新建Task/执行。该API收紧、迁移/回滚与分片见DEC-731/P04-P01进度；本项仅文档，尚未实施Schema/API。

P04-P02已实现Schema0072/ORM：新增无正文Plan/Source、Preview/Prompt/Model/精确Source数据库保护、同事务完整性、不可变/禁止截断，以及Authorization/Task/Snapshot/Invocation可空且不可变的PlanRef。旧AI/非AI Preview与旧Task保持NULL且可升降重升；一旦产生Plan历史即拒绝down。Windows 11/PostgreSQL18.6三套一次性库、Alembic drift、负例、后端2194运行/3跳过和wheel通过。Repository/Preview/写链强制绑定尚未实施。

P04-P03已实现应用Owner与PostgreSQL Repository：写前重验Plan/Envelope、仅持久化无正文证明，显式触发0072延迟完整性，读时重建强类型Plan并重算完整指纹；完全一致重放不新增，漂移失败关闭。Win11/PG18.6真实事务写/新事务读/重放/漂移/回滚与零Invocation通过，后端2197运行/3跳过及wheel通过。组件尚未装配到Preview HTTP；并发唯一冲突由P04-P04同一写服务处理。

P04-P04-A01已新增服务端Preview Plan Builder与独立Prompt规划内容合同：Task Policy、Prompt、精确Source投影、模型路由、Context/encoding/estimator全部由服务端组合，客户端不能提供派生计数/hash；正文与参数排除repr。当前为内部合同，Preview API/生产组合尚未改变。

P04-P04-A02已新增Preview规划期Prompt PostgreSQL Owner：短事务内锁定当前ACTIVE模板并读取活动版本，精确匹配部署Task Policy固定的模板/输出Schema/Context，任务参数由Policy进入PostgreSQL JSONB规范化并在数据库端计算摘要。活动版本号允许按正式Prompt激活流程推进；每次新Preview固定当时版本/hash，既有Plan不漂移。Win11/PG18.6锁、摘要、漂移和零Invocation通过；无公开API、Schema、依赖或Provider外发。

P04-P04-A03已让Document Owner提供Preview规划期精确最小投影：使用EGRESS_PREVIEW_CREATE而非执行权限，在同一事务内锁定当前成功ParseRecord/Result、读取复核私有结果并返回`minimum.document.text.v1`投影；执行期仍要求AI_TASK_EXECUTE。同步修正A01未装配合成夹具的旧策略别名，不改历史/API。Win11/PG18.6 CustomerManager权限隔离、行锁、摘要和零Invocation通过。

P04-P04-A04已把AI_TASK Preview、服务端Envelope、唯一Content Plan/Source、Audit与Receipt组合为同一事务；AI计划模式拒绝客户端派生record count/payload fingerprint，路由模型key/revision来自数据库。精确幂等重放不重读正文但必须复核Plan仍存在且摘要/计数一致，Task参数变化冲突，Audit失败全回滚。旧内部/非AI路径兼容，公开HTTP尚待A05强制新形态。

P04-P04-A05已实施公开HTTP合同收紧：AI_TASK必须提交五字段`ai_task_plan`并禁止`estimated_record_count/payload_fingerprint`；非AI operation继续要求旧派生字段且禁止Task Plan。响应合同不变，冻结基线文件/提交不回写；这是本CR/API Change的可追溯增量。合同6与后端2205回归通过，生产组合/真实HTTP-PG留A06。

P04-P04-A06已完成Windows显式生产组合：存在部署Task Policy时，Egress组合根注入Prompt规划、Document最小内容、Envelope/Plan Builder和Plan Repository，并使用统一`data_root`读取私有ParseResult；缺少Task Policy时AI_TASK失败关闭而非退回客户端摘要。Windows 11/PostgreSQL18.6真实Session/Project/Document/Prompt/HTTP链证明Preview/Plan原子一致、精确重放、旧形态400、授权201、License拒绝403和零Invocation/Provider I/O。首次证据种子使用Schema专用双花括号Prompt导致安全503，改用独立可执行Prompt后新库完整重跑。定向45、后端2206运行/3跳过及wheel通过；无Schema、依赖或客户数据外发。P04-P05继续把Authorization/Task/Snapshot/Invocation绑定同一PlanRef。

P04-P05已把Preview产生的不可变PlanRef强制传播至Authorization、Task及其授权快照，并纳入执行前置、Grant签发和Grant指纹。新AI_TASK授权若Preview无Plan、Task/快照/当前授权引用缺失或不一致、内容Plan ID与Grant不一致，均在Invocation和网络I/O前失败关闭；旧NULL历史保留可读/可撤销但不可执行。Windows 11/PostgreSQL18.6真实Preview→Authorization→Task→Preflight证明四处引用一致、重放稳定且Invocation为0；定向33、后端2209运行/3跳过及wheel通过。复用Schema0072，无Migration/API响应/依赖/外发变化。生产Invocation写入器尚未存在，下一切片P05从生命周期与持久化前置核查开始，不能把本项描述为Invocation行已落库。

P05-P01核查发现0072对Invocation只增加PlanRef外键和更新不可变守卫，0064插入守卫尚不知道该列，因而数据库不能独立拒绝新Invocation的NULL或跨Task/快照/Plan引用。应用Repository实施前先追加Schema0073 INSERT完整性守卫；旧NULL历史保留但不可继续执行，不猜测回填。该顺序是本CR原“Invocation绑定同一PlanRef”目标的失败关闭补强，不改公开API或外发范围。

P05-P02已实现Schema0073：不增加列或表，以新INSERT触发器强制每个新Invocation的PlanRef非空，并逐项核对Task、授权快照与Plan的身份和payload证明。守卫只核不可变静态证据，当前授权/License/Lease仍由应用层重验。Windows 11/PostgreSQL18.6证明旧NULL保留但新NULL、跨Plan和payload漂移拒绝，精确PENDING行可写，有新历史拒降；后端2211运行/3跳过及wheel通过。P05-P03再实现实际写入器。

## 兼容、迁移与回滚

- 原 Gate 2 冻结提交和现有 0064/0068～0071 历史不改。P03-P02-A01～A04 先建立未装配合同与 Owner，暂不产生数据库或公开 API 变化。
- P04 采用追加表/引用的全空或完整兼容迁移：旧 Preview/Authorization/Task 保留只读，但因缺少服务端 Content Plan 不可执行，也不猜测回填；新 AI_TASK 链必须完整绑定。非 AI Egress 操作不受该执行门禁影响。
- 公开 `/api/v1` 保持已有业务 source refs。AI_TASK 客户端载荷摘要字段的兼容处理必须在 P04 的 API 增量文档中明确：服务端不再信任该字段，不能用静默接受客户端摘要冒充服务端证明。
- 回滚优先撤销 Worker/AI_TASK Preview 新组合并恢复不消费；不可变 Plan、Task、Authorization、Invocation 和 Audit 历史保留。若新 Plan 已有引用，不做破坏性降级，采用向前修复或受控备份恢复。

## 验证计划与剩余风险

- 单元：规范化 fingerprint、顺序、重复/未知 Owner、Prompt/参数 hash、模板占位符、UTF-8/NFC/换行、字节与记录上限、Estimator 身份/上限。
- 集成：同一 DocumentVersion 多 ParseRecord 必须只接受 Plan 指定结果；结果 hash、Parser version、授权、Project、Context 或 Content Plan 一字节漂移均在外发前拒绝。
- Migration：空库、有旧 Preview/Authorization/Task 的升级，up/down/re-up、ORM drift、完整性和不可变负例；有新 Plan 引用时拒绝物理降级。
- 安全：正文、模板、Task 参数、storage locator、Secret 不进入 repr/log/Audit/Job/Outbox；无支持的 RAG Context 时失败关闭。
- 真实 Provider 外发不由本 CR 自动授权。本阶段只使用合成内容；客户正文外发仍需该轮明确范围与用途授权。

剩余风险是 Provider tokenizer 差异、超大解析结果的内存边界、读取期间撤权和 RAG 尚未实现。控制为 Adapter/模型绑定的 estimator、内容长度硬上限与分片策略、读取前后复核以及未支持 context policy 关闭执行。
