# RAG-03-A04-P05-P02：Embedding Batch 成功响应原子提交

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_03_A04_P05_P02_BATCH_SUCCESS_PASS`

## 目标与结论

本项为已持久化发送栅栏且响应已经统一AI层证明的Batch建立唯一成功提交路径。Schema0083和生产成功发布服务已确保Batch `RUNNING→SUCCEEDED`与精确EmbeddingRecord集合只能作为一个PostgreSQL提交事实出现；没有记录、缺记录、额外记录或身份错绑均无法提交。

## 实现边界

- 应用层复核Envelope、SendProof与ParsedResponse的Build/Batch/Job/Authorization、route/payload/source、模型、数量和维度身份。
- 仓储锁定当前Job/Lease/Attempt、Build、Index、Batch及全部source Chunk，只接受当前单次租约与精确RUNNING Batch。
- 同一事务先更新Batch成功状态、fencing token、Provider request ref和完成时间，再写入全部float32向量与域分离指纹。
- Schema0083 deferred约束在commit复核来源、记录和有效匹配数量一致，以及Chunk/正文指纹、Model、Dimension、Authorization和Provider request ref逐条一致。
- 本项没有开放READY/ACTIVE，也没有处理已知Provider失败/无效响应；后者进入P05-P03。

## 验证证据

- Windows 11 / PostgreSQL 18.6：空库迁移至0083、ORM drift无新增操作、真实事务验证通过。
- 负例：只把Batch置SUCCEEDED而不插入记录，commit失败并完整回滚至RUNNING。
- 正例：生产服务一次提交精确记录集，Batch lock version由1变2；有成功历史时降级0082被拒绝。
- 后端全量：2417项通过，3项条件跳过。
- wheel隔离：27项通过。
- wheel SHA-256：`bd3b0f5276257eaa197d4b706c027f59b3c82b53add78355481918207c48030c`。
- 外部影响：零真实Provider I/O、零客户数据外发、零Secret访问。

## 兼容、迁移与回滚

本次仅新增内部迁移、应用服务和仓储，不改变冻结`/api/v1`或依赖。无成功Batch/EmbeddingRecord历史时可降回0082；存在历史时拒绝物理降级，须停止构建并向前修复。Windows Server 2025、Debian 13、性能、READY/ACTIVE、Gate 3、UAT和正式发行包不由本项证明。
