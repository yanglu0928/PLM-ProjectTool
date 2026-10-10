# RAG-03-A04-P02 统一 Embedding 执行合同

日期：2026-10-04；状态：`RAG_EMBEDDING_EXECUTION_CONTRACT_PASS`。

新增Provider-neutral `AIEmbeddingEnvelope`、`AIEmbeddingSendProof`与`AIEmbeddingProviderAdapterPort`，确定性绑定Build/Batch、Chunk顺序/指纹、Model key/revision、route/payload/source fingerprint、字节/token与有效期。RAG模块后续只能调该统一AI边界，不得直连厂商SDK。

定向3项和后端全量2393项通过，3项环境条件跳过；wheel隔离34项通过，SHA-256 `a61a4193a6c7053fd88b7d5aa775c204c54c4a52c26765d651e5cb1b6118b137`。首轮wheel命令将Windows绝对路径误当模块名而未加载测试；改用discover pattern后重跑通过，此已如实记录。

本项零Provider I/O、零Secret解密、零客户数据外发，无Schema/API/依赖变更。下一项`RAG-03-A04-P03`实现生产OpenAI-compatible Embedding Adapter与严格向量响应校验；成功响应提交和EmbeddingRecord写入继续分项验证。
