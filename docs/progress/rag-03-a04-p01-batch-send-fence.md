# RAG-03-A04-P01 Batch 网络前持久化发送栅栏

日期：2026-10-04；状态：`RAG_EMBEDDING_BATCH_SEND_FENCE_PASS`；当前 Phase：Phase 2 Platform Core。下一项：`RAG-03-A04-P02` 统一AIService Embedding请求与本地合成Adapter边界。

## Changed

1. 新增Batch payload proof与send-fence服务；只在当前RAG单次租约中处理精确Build/Index/Batch。
2. PostgreSQL仓储在一个短事务内锁定来源Chunk、Authorization、Model、Provider及Config，重算来源fingerprint并复核数据类别/限额，才提交Batch `PENDING→RUNNING`。
3. Schema0082将同样的当前性与不变量固化为数据库守卫；已fenced历史禁止物理降级。
4. 发送栅栏回执明确为“必要但不充分”；未经后续统一AIService对Secret/端点策略的当前性复核，不允许Adapter接触网络。

## Verification

| 检查 | 结果 |
|---|---|
| Windows 11 / PostgreSQL 18.6 | `RAG_03_A04_P01_BATCH_SEND_FENCE_PASS` |
| 错误请求 | payload fingerprint错误后Batch仍为PENDING/lock0 |
| 正确栅栏 | 精确Batch原子RUNNING/token1/lock1，同Build其他Batch仍PENDING |
| 崩溃保守收敛 | 过期后已fenced Batch→UNKNOWN/`RAG_PROVIDER_OUTCOME_UNKNOWN`，未发送Batch→CANCELLED，Job不重试 |
| Migration | head0082，ORM drift无新操作，已fenced历史拒降 |
| 后端全量 | 2390项通过，3项条件跳过 |
| wheel | 隔离31项PASS；SHA-256 `73414666a86943ae4f0da933c7992191f56a9f1bc485428d803972790d213c85` |

首轮验证捕获Schema0082误将开始时间引用为不存在的`job_jobs.started_at`；已改为`job_attempts.started_at`并完整重跑通过。首轮临时数据库按fixture自动清理，无生产数据变更。

Result：PASS。本项零Provider I/O、零Secret解密和零客户数据外发。

## Known Issues / Next

尚未实现Embedding专用AIService请求/响应合同、Secret与Endpoint Policy最终发送前复核、Adapter调用、成功/失败响应提交及EmbeddingRecord写入。READY/ACTIVE、性能、Windows Server 2025/Debian 13、Gate3/UAT和正式发行包仍未由本项证明。
