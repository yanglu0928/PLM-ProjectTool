# RAG-03-A04-P05-P01 Embedding 响应证明合同

日期：2026-10-04；状态：`RAG_EMBEDDING_RESPONSE_CONTRACT_PASS`。

统一AI层新增Provider-neutral响应解析与证明：再次验证Provider request ref、model、record count、连续index、对象形状、768/1024维、有限有界数值、usage与Adapter观察值。缺少Provider id时使用`sha256:<response fingerprint>`稳定引用。

向量先规范为PostgreSQL pgvector实际存储的IEEE-754 float32，再以`plm-embedding-vector-float32.v1`域、维度和big-endian向量字节计算SHA-256；解析结果中的向量与指纹不进入repr。该选择消除Python float64/JSON表示与数据库float32之间的指纹漂移。

验证：响应正向、稳定指纹、缺id回退及model/index/dimension/NaN/id/usage负例通过；Adapter同步拒绝非法id。后端全量2411项通过、3项条件跳过；wheel隔离9项，SHA-256 `5ab86c70645c91cea7fed48dde580dcdd3a0f026598911190bda1241dd08e80c`。零真实Provider I/O、Secret访问或客户数据外发。

兼容与回滚：无Schema、公开API和依赖变化；可回退新合同并保持成功提交关闭。下一项`RAG-03-A04-P05-P02`新增Schema0083，要求Batch成功状态、全部EmbeddingRecord与响应证明同事务提交；READY/ACTIVE、性能和Gate3继续独立验收。
