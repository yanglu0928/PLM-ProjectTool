# RAG-03-A04-P06：Embedding 单次 Batch Worker

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_03_A04_P06_BATCH_WORKER_PASS`

## 结论

单次Batch Worker已把双重当前授权、Secret访问、持久化发送栅栏、一次Adapter调用、严格响应解析及成功/失败发布组合起来。提交器使用的route/proof与实际发送时第二次pre-send授权完全相同，不进行发送后重查或猜测。

## 结果分流

- `BATCH_SUCCEEDED`：响应严格有效，Batch与精确float32 EmbeddingRecord集合原子提交。
- `BUILD_FAILED`：完整HTTP拒绝或响应无效，按Schema0084原子关闭Build聚合且不重试。
- `RECONCILIATION_PENDING`：网络结果、返回值或本地提交结果不确定；保留持久RUNNING栅栏，Worker不重发，由已验证的租约过期对账收敛UNKNOWN。
- 所有响应缓冲区均在Worker退出路径关闭；敏感正文/Secret不进入结果或日志。

## 验证证据

- Windows 11 / PostgreSQL 18.6：三份全新隔离库验证成功、无效响应、UNKNOWN路径。
- 成功路径：一次合成Adapter调用，使用最终授权，Batch SUCCEEDED并写精确记录集。
- 无效路径：一次调用，响应SHA-256保留，Build原子FAILED，零向量、零重试。
- UNKNOWN路径：一次调用后不重放、不虚报终态，Batch保持RUNNING供既有过期对账。
- 后端全量：2428项通过，3项条件跳过。
- wheel隔离：36项通过；SHA-256 `f81a2bf78e288887cf1654379e7fe8de4f2aab6fe15bb774ec7cd909ed5f3c76`。
- 全部使用本地合成Adapter，零真实Provider I/O、零客户数据外发。

## 偏差与下一项

首轮验证查询中的`LIKE 'sha256:%'`未按psycopg参数占位规则转义，属于验证夹具错误；改为`%%`并用新隔离库完整重跑，未修改产品逻辑或数据库守卫。本项无Schema/API/依赖变化。下一项`RAG-03-A05-P01`核查完整记录集、HNSW计划、质量证据、Build完成和READY/ACTIVE原子边界；多批调度、Server2025/Debian13、性能、Gate3、UAT和正式发行包仍待独立证明。
