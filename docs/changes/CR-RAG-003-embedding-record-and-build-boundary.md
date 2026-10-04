# CR-RAG-003：EmbeddingRecord、受控 HNSW 与构建发送边界

日期：2026-10-04；状态：`APPROVED_FOR_IMPLEMENTATION_BY_STANDING_AUTHORIZATION`；WBS：`RAG-03-A01～A05`。关联 Gate 2 冻结 ADR-004、DM-04、SC-02～04、API-03，以及 CR-RAG-002/Schema0077；原冻结提交 `64cdf09` 不改。

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
