# RAG-03-A04-P05-P03：Embedding 已知失败原子收敛

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_03_A04_P05_P03_BATCH_FAILURE_PASS`、`RAG_03_A04_P05_P03_PROVIDER_REJECTED_PASS`

## 结论

Schema0084和生产失败发布服务已为当前fenced Batch建立两条不可重试终态：完整HTTP非200响应作为已知Provider拒绝且不伪造响应引用；严格解析失败保留`sha256:`响应证明。两条路径都在同一事务关闭Job、Lease、Attempt、Build、Index、当前Batch、后续未发送Batch和Audit，且不写EmbeddingRecord。

## 关键边界

- 只有当前单次RAG租约、精确Envelope/SendProof/Batch身份可进入失败发布。
- Provider拒绝使用`RAG_PROVIDER_REQUEST_REJECTED`；无效响应使用`RAG_EMBEDDING_RESPONSE_INVALID`。
- 当前RUNNING Batch变为FAILED；后续PENDING Batch以`RAG_BUILD_ABORTED_AFTER_BATCH_FAILURE`取消；先前SUCCEEDED历史不改写。
- Jobs Owner以`retryable=false`释放租约并终结Job/Attempt；Build与Index随后同事务FAILED。
- SYSTEM Audit与所有状态一起提交，任一步失败整体回滚。
- 网络超时、断连及栅栏后不确定异常仍是UNKNOWN，不得借本路径伪装为已知失败。

## 验证证据

- Windows 11 / PostgreSQL 18.6：两份全新隔离库分别验证无效响应与Provider拒绝；ORM drift无新增操作。
- 无效响应：保存响应SHA-256，当前Batch FAILED、另一未发送Batch CANCELLED、零向量、完整Audit。
- Provider拒绝：Provider request ref保持NULL，同一聚合原子失败、零向量、不可重试。
- 有上述历史时降级0083被拒绝。
- 后端全量：2422项通过，3项条件跳过。
- wheel隔离：30项通过；SHA-256 `c02440eb5d569aa9ed8b129af169c5e55b7861dffe2ba31ecc74b2c017df119b`。
- 外部影响：零真实Provider I/O、零客户数据外发、零Secret访问。

## 兼容与下一项

本次为内部Migration、应用/仓储和错误分类增量，不改变冻结`/api/v1`或依赖。无新失败历史时可降0083；有历史时向前修复。下一项`RAG-03-A04-P06`组合单次Worker，明确成功、已知失败、UNKNOWN和提交不确定四类结果；READY/ACTIVE、性能、Server2025/Debian13、Gate3、UAT和正式发行包仍未由本项证明。
