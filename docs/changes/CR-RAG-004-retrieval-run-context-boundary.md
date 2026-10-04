# CR-RAG-004：RetrievalRun、加密查询内容与最小 Context 边界

日期：2026-10-04；状态：`A05_P02_RETRIEVAL_WORKER_CONTEXT_PASS`；WBS：`RAG-04-A01～A06`。关联 Gate 2 冻结 ADR-004/009、DM-04、SC-01～04、API-03，以及 Schema0087/CR-RAG-001～003；原冻结提交 `64cdf09` 不改。

## 差异与实施方案

冻结基线已经定义 RetrievalRun、Candidate/ScorePart、ContextBundle/Item 和异步项目 API，但生产仓库尚无这些 Owner。现有 Job 安全合同只允许引用类 `payload_refs`，不能承载 query；冻结 API 又要求 POST 后异步执行。因此需要在不改变 API 的前提下细化查询正文的持久化 Owner。

按持续授权采用以下增量方案：

1. 新增 RAG 自有 `RetrievalQueryContent` 密文实体，使用独立注入的 AEAD 数据加密端口、版本化 AAD、密钥引用和 query fingerprint；不复用 Secret 业务表，不把明文写入 Run、Job、Outbox、Audit、日志、DTO 或异常。
2. 新增冻结 SC-01 已列出的 Run/Candidate/Context/ScorePart 物理实体。Run 固定 Scope/Project/Actor、实际 Index/Model/Policy generation、Job、query/filter 指纹、rerank/egress/degraded/quality 状态；候选和 Context 都是不可变快照。
3. PROJECT 与 GLOBAL 分开授权、召回和计分，再由版本化策略合并。PROJECT 的候选、Rerank、Context 与 AI 消费每层都重新证明相同 ProjectId；GLOBAL 只允许策略登记的来源类型。
4. metadata filter 采用固定字段/操作符 AST 和参数化 SQL，拒绝 SQL、JSONPath、任意 key/column/expression。候选不足只能在同 Project/Index 扩大扫描或 exact/FTS fallback。
5. Context 表不复制无界正文，只固定 Chunk、DocumentVersion/Evidence locator、授权截取范围、顺序、token budget 与指纹；读取时按当前访问权和不可变来源投影最小 snippet。
6. Query Embedding/Reranker 若外发，必须复用统一 AIService 的 Egress Preview/Authorization、当前 Secret/路由与发送栅栏；没有授权时失败关闭。纯数据库 FTS/exact 显式记录 `NOT_APPLICABLE`。

## 风险、兼容、迁移与回滚

- 密钥风险：正式运行账户必须提供专用内容加密密钥；缺失、错误版本或解密失败时停止创建/执行，不回退明文。Windows 11 先用隔离临时密钥证明机制；正式信任源另以部署证据关闭。
- 隔离风险：所有 PROJECT 子表同时保存并复合绑定 ProjectId/Run/Index/Chunk，应用和 deferred constraint 双重校验；错误项目统一安全错误，不披露存在性。
- 质量风险：隔离合成 ACTIVE 只用于机制测试；正式无 ACTIVE 时请求失败，不把 READY、旧 generation 或历史 PoC 结果当作可用索引。
- 兼容：追加内部 Schema 和 Owner，保持冻结 `/api/v1` 路径/DTO；不引入 Redis、队列、独立向量库、本地模型或 Runtime DDL。
- 迁移：Schema0088 先落不可变基础并关闭状态转换，再逐项开放创建、执行和完成 Owner。空表可降；存在密文、候选或 Context 历史时拒降。
- 回滚：可停止新 Retrieval Job 和 HTTP 挂载；已产生的运行/审计历史保留并向前修复，密文按 R3 保留策略受控清理，不能删除历史来伪装回滚。

## 验证计划

Windows 11/PostgreSQL 18.6 验证空库/有数据升降重升、ORM drift、密文无明文泄漏、Run/Job/Index/Project 复合绑定、不可变候选/分数/Context、跨项目/旧 generation/任意 filter/无 ACTIVE/撤权/过期 License 负例及 Audit 失败全回滚。Owner 完成后以明确标记的合成 ACTIVE 验证 FTS/vector/exact、GLOBAL/PROJECT 合并、Rerank degraded 与最小 Context；不冒充业务质量。Windows Server 2025、Debian 13、20 并发/P95、正式密钥、真实业务质量、Gate 3/UAT 和发行包继续按独立证据关闭。

## A01 核查结论

静态检查确认当前只有 Chunk/Embedding/Index 实现和 AI 侧 `RAG_CONTEXT` 失败关闭合同，没有 RetrievalRun/ContextBundle 生产 Owner。冻结边界可在不破坏 API 的前提下通过专用加密 QueryContent 和追加式不可变表实现；下一项进入 Schema0088，未产生真实外发或客户数据处理。

## A02-P01 实施与结果

Schema0088/ORM已新增Run、密文QueryContent、Candidate/ScorePart及ContextBundle/Item。Run/Job不保存query正文；同事务deferred约束拒绝缺QueryContent。PROJECT候选复合重验Run、ACTIVE Index、精确source Chunk与AVAILABLE Embedding；Score固定整数微分值；Context只存引用/范围/token/指纹且完成Owner前关闭。六张表历史不可改删截断，有任一历史拒降。

Windows11/PostgreSQL18.6完成空/已有基础数据升级、drift、空历史降级重升、有历史拒降及合成ACTIVE组合；缺QueryContent、状态直改和提前Context被拒绝。后端2458/跳过3、wheel RAG86通过，SHA-256 `4fb5d1c4f465be331807cc1dcbcbddd8746216fe641d881bb22224e2c643b4fc`。无真实Provider I/O或客户数据外发；合成ACTIVE不作业务质量证据。进入A02-P02创建Owner。

## A02-P02 实施与结果

实现仅允许`fts.project.v1 + none.v1`的受权创建Owner和专用AES-256-GCM Query Cipher。输入规范化后，在同一业务事务内重验Session/CSRF、License、当前Project成员、ACTIVE Index/Model/Chunk及幂等收据；只有非重放且当前授权的请求才读取密钥并加密。Job、Run、QueryContent、Audit和收据同事务，重放仍重验当前权限，query缓冲归零。

Windows11/PostgreSQL18.6完成成功创建、Audit失败全回滚、幂等重放、撤权后重放以及CSRF/License/Index负例；query明文未进入Job/Audit。后端2467/跳过3、wheel RAG95通过，SHA-256 `14a6a8ce6b7293e63acbb7f40a15bbb513ba938a8649ea978b138b9420a0fe12`。零真实Provider I/O、零客户数据外发；合成ACTIVE仍不作Gate证据。进入A03-P01执行链前置核查。

## A03-P01 核查结论

静态检查确认通用Job claim/过期处理当前只隔离`rag/RAG_INDEX_BUILD`，会错误接管`rag/RAG_RETRIEVAL`并可能让Job与Run状态分裂。A03先增加专属单次claim，同时从通用ready/expired路径排除Retrieval；过期Run须等待专属原子Reconciler，不允许通用重领。

执行边界锁定为：当前Lease/License/原请求Actor与Membership/ACTIVE Index/Model/来源重验通过后才能解密；query重新计算fingerprint并归零；首个`fts.project.v1`只生成同Project、同Index generation、参数化SQL和固定metadata AST的有界内存候选，A05再把Candidate/Score/Context及Run/Job终态原子发布。vector/exact Query Embedding、GLOBAL合并和Rerank外发仍关闭并留给A04。未运行新增程序测试，进入A03-P02专属claim与通用队列隔离。

## A03-P02 实施与结果

新增`RAG_RETRIEVAL`专属单次claim DTO/Service/PostgreSQL仓储，固定PROJECT scope、唯一Run引用payload、Run ID幂等键、原Actor/Trace及attempt/fencing均为1；当前检查点可重验同一Lease。通用ready/expired claim新增Retrieval排除，Parser/AI/RAG Build入口也不能跨Owner接管；专属入口不自动重领过期generation。

Windows11/PostgreSQL18.6合成组合证明四类非本Owner不抢占、专属Worker精确认领、第二Worker不重复领取，且租约过期后Job/Lease/Run保持原generation等待原子对账。定向16、后端2473/跳过3、wheel RAG100通过，SHA-256 `5d463c4c635d33a2607a9cd0985a7969d633ba9569ef49c719c94f6078977013`。无Migration/API/依赖/Provider I/O/客户数据外发；进入A03-P03当前事实重验与受控解密。

## A03-P03 实施与结果

新增当前事实重验/受控解密服务与仓储：先以原请求Actor无密钥检查User、Project/Membership/Department和License，再重验同一Lease/角色并有序锁定Run、ACTIVE Project Index、精确来源Chunk、AVAILABLE Embedding及QueryContent。只有全链一致才读取一次密钥；解密后严格UTF-8/NFKC复算query fingerprint，受权callback结束或异常即归零。授权快照以安全引用和指纹固定，不记录正文。

同时修正A02入口与既定边界不一致：当前唯一`fts.project.v1 + none.v1`拒绝非空GLOBAL Index，防止创建Worker必然拒绝的悬挂作业；未来GLOBAL合并仍由A04显式开放。Windows11/PostgreSQL18.6成功路径及成员撤权/License关闭零密钥读取负例通过；新增5、相关17、后端2478/跳过3、wheel RAG105，SHA-256 `32fd62d069d23df52423d2a7e398ac8662c948740fbbb7da9fd120e6372eb9e3`。无Migration/API/依赖/真实外发，进入A03-P04参数化PROJECT FTS。

## A03-P04 实施与结果

新增参数化PROJECT FTS Planner/Repository：`simple` websearch query只经bind parameter传入，固定限制受权Project/Index/Model/精确来源、ACTIVE Chunk、AVAILABLE Embedding/DocumentVersion和ACTIVE Document。metadata只映射category/source type/version三个字段；business/effective在有正式物理语义前关闭。rank量化整数并以source ordinal/ChunkId稳定排序，池上限400。

输出只是不含正文/向量的不可变内存候选，A05前不写Candidate/Score。Win11/PostgreSQL18.6返回一条精确同范围候选且数据库候选表保持空；新增3、相关13、后端2481/跳过3、wheel RAG108，SHA-256 `df2f916abbd8d04c7ebe51d35eda55bb86b307ff5250470943f1e6e68ce7129f`。无Migration/API/依赖/外发；A03完成，进入A04-P01。

## A04-P01 核查结论

当前`fts.project.v1 + none.v1`确定为完整零外发策略，不是缺vector/rerank后的degraded。P02只做整数FTS分数的稳定Top-K和显式quality plan：1至Top-K不足可成功并标`CANDIDATE_SHORTFALL`，零候选以`RAG_NO_AUTHORIZED_CANDIDATES`失败且不创建空Context；任何不足都不得跨Project、旧Index、放宽filter或自动外发补齐。

GLOBAL/vector/exact query embedding/rerank必须使用新策略版本并先完成Egress授权/发送/响应绑定，保持关闭且不阻塞首个FTS闭环。本项仅文档，未运行新增程序测试；进入A04-P02纯应用合并计划。

## A04-P02 实施与结果

新增纯应用FTS merge plan：整数分数稳定Top-K，每条生成FTS/FINAL ScorePart；非零不足标`CANDIDATE_SHORTFALL`但不degraded，零候选抛`RAG_NO_AUTHORIZED_CANDIDATES`，rerank/egress保持NOT_APPLICABLE。无数据库写入、网络或外发。

新增4、相关7、后端2485/跳过3、wheel RAG112通过，SHA-256 `41cbb1c460c6874fe5d4c16ce3cee8a764f44ed7f72ad878cf23d4a403517942`。A04当前FTS策略完成，进入A05-P01 Schema0089原子终态边界。

## A05-P01 实施与结果

Schema0089把Retrieval成功、正常失败和租约过期统一收敛为提交期原子边界。成功必须在同一事务内完成同generation的Job/Attempt/Lease/Run，并写入1..Top-K个Candidate、每候选恰好两条FTS/FINAL ScorePart、唯一`project-documents.v1` ContextBundle及与候选完整同序的ContextItem；不足只允许`CANDIDATE_SHORTFALL`。失败只允许固定错误码，要求终态同步且结果集为零。RUNNING Run不能提交结果行，所有结果还必须由当前终态事务创建，关闭半快照和旧generation补写。

Windows11/PostgreSQL18.6完成0088已有库升级、drift、空历史降级重升、完整成功、零候选失败、过期generation失败、Candidate单独提交拒绝、缺Context成功拒绝及终态历史拒降。相关32、后端2490/跳过3、wheel RAG117通过，SHA-256 `9c34322accd117ea004fd4d26eaa0ff5643f4541797de56babb6b28041a0bde1`。无公开API/依赖/网络/外发；合成ACTIVE不作业务质量证据。进入A05-P02发布Owner、单次Worker与AI `RAG_CONTEXT`受权读取。

## A05-P02 实施与结果

新增成功/已知失败/过期发布Owner与一次性Worker：当前Actor/License/Lease/Run/ACTIVE Index及来源重验通过后受控解密，执行参数化PROJECT FTS和稳定合并，再在同一事务提交Job/Attempt/Lease/Run、完整结果和SYSTEM Audit。提交结果不确定时只进入`RECONCILIATION_PENDING`，不自动重放。过期generation由专属Reconciler关闭且不重领。

新增AI `RAG_CONTEXT`读取Owner与策略注册边界：只按精确Run/Bundle读取，在当前`AI_TASK_EXECUTE`授权和License双检查之间锁定并复核完整最小Context来源、顺序、locator、snippet/token/bundle fingerprint；调用方不能自行注入RAG正文。实施中修正零分FTS候选与Schema0089正分约束不兼容的偏差：非正分在merge前过滤，全零集合固定失败且不创建结果。

Windows11/PostgreSQL18.6真实事务完成成功Worker/Audit/Context读取、撤权关闭、零候选失败、过期对账及失败零结果；RAG125、AI定向8、后端2498/跳过3、wheel隔离RAG125+AI8通过，SHA-256 `71116eb41d492a683bc85372d01dbc9784366eb298f700c729b9adc4772cbbdd`。无Migration/公开API/依赖/网络/外发；合成ACTIVE不作业务质量证据。进入A06-P01 HTTP/权限/组合前置核查。
