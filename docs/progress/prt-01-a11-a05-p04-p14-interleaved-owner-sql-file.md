# PRT-01-A11-A05-P04-P14：独立客户端交错负载与分段诊断

2026-10-08 / 状态：`DIAGNOSTIC_COMPLETE_PERFORMANCE_FAIL`。

编码前检查：Phase 2；输入为 P12/P13 独立客户端基准、CR-PRT-005 与 Windows 11 隔离 PostgreSQL 18.6/pgvector、合成 Approved Prototype/Review/Trace/文件夹具。只扩展隔离验证脚本，不改生产程序、池参数、Schema、API、权限或文件证明。验收为默认池→临时 20+0 池→默认池交错顺序，相同 20 并发、两项预热/三轮、HTTP 200/强 ETag/PROTOTYPE 断言，并在临时池下独立记录阶段、SQL、文件耗时。阶段嵌套、SQL 并行总和及文件时间不可相加为端到端耗时；计时器本身可能扰动负载。

隔离真实 Uvicorn/PG 脚本两轮均退出 0。第一轮两项（`PROTOTYPE_SCOPE_DECISIONS`/`PROTOTYPE_COVERAGE`）三轮近秩 P95 中位：默认前约 641/663 ms、临时池约 584/568 ms、默认后约 640/652 ms。第二轮：默认前约 645/675 ms、临时池约 651/557 ms、默认后约 705/639 ms。两轮临时池均未使两项同时达到 ≤500 ms；首项第二轮无稳定改善。计时器仅包装临时池和默认后段，默认前段未包装，故本交错结果只能说明性能仍失败，不能把池差值作为独立因果量或据此改变生产池。

第二轮临时池 122 次资格 GET：预览服务方法 P95 约 557 ms、Prototype Owner 约 529 ms、其中 Requirement Owner 约 254 ms、Prototype Review/Artifact 子阶段约 183 ms；这些是重叠墙钟区间，峰值并行分别为 20/20/18/17。SQL 事件 7076 次（58 次/资格）、执行时间求和约 47.83 秒、单语句 P95 约 14.11 ms；文件本体证明 122 次、求和约 5.52 秒、单次 P95 约 70.84 ms。SQL 与文件都受并发和事件包装影响，不能直接从总耗时或 P95 扣减得到端到端收益，也不能为了性能跳过当前性、授权、Review、文件字节证明。

本项无生产升级/迁移；撤 P14 探针即可回滚，历史不变。P15 应在同一事务锁语义下核对 Prototype Owner/Requirement Owner/Review 的 58 条查询中可安全合并的重复读取，先记录候选与等价性，再决定是否编码；若无可证安全收益则保持性能 FAIL，转向独立任务。Prototype 正常生产入口继续关闭，Gate 3/UAT/可用包未通过。

TraceLink：CR-PRT-005 → P12/P13 → P14 → DEC-20261008-1087 → P15。
