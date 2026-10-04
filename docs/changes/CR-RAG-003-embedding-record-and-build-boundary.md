# CR-RAG-003：EmbeddingRecord、受控 HNSW 与构建发送边界

日期：2026-10-04；状态：`A04_P01_IMPLEMENTED_AND_WINDOWS11_PG18_VERIFIED`；WBS：`RAG-03-A01～A05`。关联 Gate 2 冻结 ADR-004、DM-04、SC-02～04、API-03，以及 CR-RAG-002/Schema0077；原冻结提交 `64cdf09` 不改。

## 差异与实施方案

冻结基线要求 EmbeddingRecord 固定 Index/Chunk、模型/维度、向量指纹、状态、Provider 请求引用与外发授权，并通过受控维度 HNSW、构建校验和原子激活形成闭环。当前生产仓库只具备 PLANNED Index 与精确 Chunk 快照，没有 Python `pgvector` 类型适配、EmbeddingRecord、构建 Owner、外发批次栅栏或激活证据。

按用户持续授权，本变更采用以下增量方案：

1. 正式后端加入 [`pgvector==0.5.0`](https://pypi.org/project/pgvector/)。它只提供 Python/SQLAlchemy/Psycopg 类型适配，不替代 PostgreSQL 端已锁定的 pgvector extension 0.8.6；许可证清单登记 MIT，但正式第三方 Notice 复核完成前不解除发行阻塞。
2. EmbeddingRecord 使用逻辑无界 `vector` 列，并以 `vector_dims(vector)=embedding_dimension`、Index/Chunk/模型/维度复合约束和不可变守卫固定事实。成功向量记录为 `AVAILABLE`；失败尝试保留在构建批次/Job 证据中，不制造无向量的 AVAILABLE 记录。
3. 首版仅由 Migration 为已验证模型维度 768、1024 建立表达式 HNSW 索引；未知维度即使不超过 2,000，也只能保持 PLANNED 并在构建/激活前失败关闭。Runtime Role 禁止执行 DDL，不根据模型输入动态创建索引。
4. Index 构建必须由唯一 Build Owner 将 PLANNED 推进为 BUILDING，逐批绑定固定 Index、source snapshot、Chunk 集合、模型、授权和 payload fingerprint。每个批次在网络调用前先提交 RUNNING/发送栅栏；若发送后结果未知，标记 UNKNOWN/FAILED 且禁止自动重发，除非后续能证明 Provider 幂等键语义并另行变更。
5. 仅在所有 source Chunk 恰好各有一条有效记录、维度/模型/指纹一致、HNSW 执行计划与质量检查满足门槛后，Index 才可 READY；ACTIVE 切换必须保持同 Scope/Project/purpose 唯一，并重新验证模型、授权与来源当前可用性。

## 风险、兼容、迁移与回滚

- 重复外发/费用风险：批次发送前持久化栅栏，网络结果未知不自动重发；取消和显式重建均创建新 generation，不复活旧批次。
- 维度风险：768/1024 来自现有 PoC 模型证据；其他维度无预建 HNSW，不以顺序扫描冒充生产可用。
- 绑定风险：Schema0078 将为 Index 增加 `(id, embedding_dimension)` 唯一键供 EmbeddingRecord 复合外键使用，避免记录维度与 Index 漂移。
- 兼容：内部 Schema/依赖增量，不破坏 `/api/v1`；不引入 Redis、消息队列、独立向量库、本地模型或 Runtime DDL。
- 迁移：先安装锁定依赖，再执行 Schema0078；已有 PLANNED Index 不自动构建。空表允许降级；存在 EmbeddingRecord/构建历史时拒绝物理降级，采用停止构建、向前修复或受控恢复。
- 回滚：依赖可随空表降级移除；任何已产生向量/外发证据均作为审计历史保留，不通过删除伪造回滚。

## 验证计划

Schema0078 在 Windows 11/PostgreSQL 18.6 完成空库与已有 Index 升/降/重升、ORM drift、768/1024 向量/HNSW、错误维度/模型/Chunk/Scope、重复记录、不可变和有数据拒降负例；确认 PLANNED 状态仍无法插入向量。后续 Build Owner/Adapter 使用合成本地 Provider 先验证发送栅栏、授权撤销、未知结果、批次边界、READY/ACTIVE 原子性，再进行经明确授权的真实质量复验。Windows Server 2025、Debian 13、性能、Gate 3/UAT 和正式发行仍按独立证据关闭。

## A01 核查结论

现有 `pyproject.toml` 未包含 Python `pgvector`，生产 AI Adapter 只实现 Chat 类调用，Schema0077 又故意封闭全部状态更新，因此当前没有隐式可执行的 Embedding 路径。PyPI 的 `pgvector` 0.5.0 支持 Python 3.10+、SQLAlchemy 与 Psycopg，满足 Python 3.13 技术栈；PoC 已使用 768 与 1024 维模型。A02 先落 EmbeddingRecord/HNSW 数据边界，且在 Build Owner 落地前保持零可写路径，不把 Schema PASS 描述为构建或质量 PASS。

## A02 实施与结果

Schema0078 已加入 `rag_embedding_records`、Index/模型/维度和精确 source Chunk/正文指纹复合外键、外发授权引用、向量/来源 SHA-256、不可变/保留守卫，以及 768/1024 两个 cosine HNSW 表达式索引。`pgvector==0.5.0` 已进入正式依赖；Index 仍由 Schema0077 锁定为 PLANNED，因此数据库守卫要求 BUILDING 的 EmbeddingRecord 当前没有可写生产路径。

Windows 11/PostgreSQL18.6 完成空库升降重升、已有 Index 升级、ORM drift、PLANNED 写关闭、768/1024 HNSW 物理执行计划、维度负例、不可改写/删除/截断和有数据拒降；标记 `RAG_03_A02_EMBEDDING_RECORD_SCHEMA_PASS`。源码后端全量2362项通过、3项既有条件跳过；wheel 隔离导入与20项本次Schema/迁移合同通过，SHA-256 `6adfdd88423491bb4d44c4f95992e14602efc11e5455feb26acbc003fa5ab5ba`。无真实 Provider I/O、Secret 或客户数据外发；Build/批次/READY/激活仍待A03～A05。

## A03-P01 实施与结果

Schema0079 新增不可变 `rag_embedding_builds` 与 `rag_embedding_build_batches`。每个 Index 只能有一个 generation=1 Build 根和一个 `rag/RAG_INDEX_BUILD` Job，Job `max_attempts=1`；所有 Batch 必须与 Build 同事务创建、ordinal/range 连续覆盖精确 Index 来源，每个 Batch 独占一次 INDEX_BUILD/INDEX_REBUILD Authorization，且Scope/Project/Model、数据类别、记录/字节/token上限、source/payload fingerprint完全匹配。授权集合和Build fingerprint在提交时复算。

Build/Batch当前只允许PLANNED/PENDING创建，UPDATE/DELETE/TRUNCATE均关闭；所以Schema完成后仍不会启动Job、推进Index或发生外发。Windows11/PostgreSQL18.6完成空库升降重升、已有Index升级、ORM drift、有效双批计划、Job Owner/逐批授权/来源覆盖、状态关闭、历史保留和有数据拒降；标记`RAG_03_A03_P01_BUILD_PLAN_SCHEMA_PASS`。后端2366项通过/3跳过；wheel隔离定向24项，SHA-256 `94d7bddb4b89811f3e630d91c1e8d1360281d32d8dfc3420423ffe716d91c535`。P02将实现受权创建/claim与PLANNED→BUILDING原子推进。

## A03-P02 实施与结果

新增内部 `RAGEmbeddingBuildPlanner`，从固定 PLANNED Index 派生 Build/Job/Batch，应用层先验证连续分批和授权唯一性，数据库再重算来源、授权集及 Build fingerprint。新增 Jobs-owned `RAGIndexBuildClaim`：只领取 `rag/RAG_INDEX_BUILD`，严格要求 generation/attempt/fencing token 均为1、精确 payload/idempotency/scope/project/actor/trace 且租约当前有效。

Schema0080 仅开放持有当前租约时的 Build `PLANNED→RUNNING` 和 Index `PLANNED→BUILDING`，两者必须在同一事务完成；启动时重验 Model AVAILABLE、Chunk ACTIVE、逐批 Authorization 未撤销/未过期。同时收紧 EmbeddingRecord 守卫：记录必须归属于已 SUCCEEDED 且授权引用精确匹配的 Batch；P02 尚未开放 Batch 转换，因此无半实现向量写入路径。

Windows11/PostgreSQL18.6 标记 `RAG_03_A03_P02_BUILD_BEGIN_PASS`：实际完成受权双批计划、Parser/AI Owner隔离、RAG单次claim、Build/Index原子启动、PENDING Batch向量拒绝、未开放Batch状态拒绝与已启动历史拒降；ORM drift无新操作。后端2378项通过/3跳过；wheel隔离22项，SHA-256 `cdeeb0404194cd6c2c00d013e48d6d1477b2c797411e6eef4554be31ace30056`。无Provider I/O、Secret或客户数据外发。P03将先关闭单次租约过期后 Job FAILED 与 Build/Index 状态收敛，再进入批次发送栅栏。

## A03-P03 实施与结果

新增 `ExpiredRAGEmbeddingBuildReconciler`和Schema0081。过期RUNNING RAG Job被排除在通用claim及RAG再claim之外，只能由Reconciler使用PostgreSQL时间和当前generation证明处理。单事务将Lease置EXPIRED、Attempt/Job置不可重试FAILED、Build/Index置FAILED、未发送PENDING Batch置CANCELLED，并写入唯一SYSTEM Audit；Audit或系统身份失败必须整体回滚。Schema同时预留RUNNING Batch→UNKNOWN的保守收敛，后续发送栅栏实现后再做实际正向验证，不将本项描述为已验证网络未知结果。

Windows11/PostgreSQL18.6 标记 `RAG_03_A03_P03_EXPIRED_RECONCILIATION_PASS`：实际验证Audit失败六类聚合全回滚、随后一次原子失败收敛、两个未发送Batch取消、SYSTEM Audit、旧Worker续租拒绝和已对账历史拒降；零Provider I/O。后端2384项通过/3跳过；wheel隔离25项，SHA-256 `1df2985741d742aca64516b24f27eb4b868e7c84f1b5377533fe1a2a3357d70b`。A03完成，下一项进入A04-P01批次网络前持久化发送栅栏。

## A04-P01 实施与结果

新增 `RAGEmbeddingBatchSendFenceService`和Schema0082。Worker必须在同一短事务中锁定当前Job/Lease/Attempt、RUNNING Build、BUILDING Index和精确PENDING Batch，重验payload/来源指纹与限额、Chunk ACTIVE/Scope/数据类别、未撤销且未过期的逐批授权、AVAILABLE Embedding Model、ACTIVE Provider及其当前可Embedding Config，然后才持久化 `PENDING→RUNNING`、fencing token和开始时间。事务提交后的回执仅是必要边界，不单独授权Provider调用；A04-P02仍须通过统一AIService复核Secret/端点策略并调用Adapter。

Windows11/PostgreSQL18.6标记 `RAG_03_A04_P01_BATCH_SEND_FENCE_PASS`：错误payload指纹不产生状态变化，正确批次原子提交RUNNING，另一批保持PENDING；模拟租约过期后已fenced批次实际收敛为UNKNOWN/`RAG_PROVIDER_OUTCOME_UNKNOWN`且Job不重试，未发送批次取消，已fenced历史拒降。后端2390项通过/3跳过；wheel隔离31项，SHA-256 `73414666a86943ae4f0da933c7992191f56a9f1bc485428d803972790d213c85`。本项零Provider I/O、零Secret解密和零客户数据外发。

## A04-P02 实施与结果

统一AI模块新增Provider-neutral `AIEmbeddingEnvelope`、`AIEmbeddingSendProof`和`AIEmbeddingProviderAdapterPort`。Envelope以规范UTF-8 JSON固定外发文本顺序、Model key/revision和请求schema，另以source fingerprint绑定Chunk id/原ordinal/正文指纹；SendProof同时绑定Build/Batch/Job/Authorization、fencing token、route/payload/source fingerprint、字节/token与有效期。敏感正文和指纹字段不进repr。

本地合成Adapter验证正确proof仅调用一次，route/payload/source/过期/顺序漂移全部失败关闭。后端2393项通过/3跳过；wheel隔离34项，SHA-256 `a61a4193a6c7053fd88b7d5aa775c204c54c4a52c26765d651e5cb1b6118b137`。首轮wheel命令误把Windows绝对文件路径当作Python模块名，测试未加载；改用discover pattern后3项通过，同一wheel的31项RAG测试也通过。本项零Provider I/O、零Secret解密和零客户数据外发。

## A04-P03 实施与结果

新增 `PinnedHttpsOpenAICompatibleEmbeddingAdapter`，并将原Chat Adapter的DNS隔离、公网IP候选全部验证、固定443、系统CA/TLS1.2+、禁代理/重定向、连接/读/总超时及有界Content-Length JSON收发抽为共用pinned TLS核心。Embedding wire只映射已授权的model/input及float编码；响应必须精确匹配记录数、0起连续index、模型、768/1024维和有限有界数值，usage形状也必须合法。

定向11项及旧Chat安全回归通过；后端2396项通过/3跳过；wheel隔离37项Embedding/RAG与5项Chat Adapter，共42项通过，SHA-256 `dde88638911bff74e9b2877752297d6a60f291e0c6548ac8661f319602fec7e8`。全部使用合成socket，零真实Provider I/O、零Secret解密和零客户数据外发。

## A04-P04 实施与结果

新增当前路由事实仓储、Embedding pre-send与send-once服务、Scope感知Secret审计及RAG fence桥接。一次调用必须依次完成：当前事实授权、精确Secret版本访问、Secret作用域内再次授权、事实稳定性比较、持久化Batch fence、单次Adapter调用。两次授权各在事务内外检查License；fence后的任何异常均按Provider结果未知处理，禁止自动重放。

为让统一AI模块无歧义生成RAG fence proof，内部Envelope补充EmbeddingIndex id、batch ordinal和source first ordinal；这些身份不进入厂商JSON，不改变最小外发正文或payload fingerprint。Windows11/PostgreSQL18.6标记`RAG_03_A04_P04_EMBEDDING_SEND_BOUNDARY_PASS`：真实事务完成双重授权、活动Secret版本证明、PROJECT Secret审计、PENDING→RUNNING fence、一次合成Adapter调用及明文归零。后端2408项通过/3跳过；wheel隔离21项，SHA-256 `16e3e4f1273606488b1913ea2b1bdca530c7c934df055e5a5c41a77a4bd639da`。首轮验证在Build启动后更新payload被Schema0082不可变守卫正确拒绝，验证改为计划前生成精确payload后使用新库重跑通过；未放宽数据库。零真实Provider I/O、零客户数据外发。
