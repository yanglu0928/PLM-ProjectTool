# RAG-03-A03-P03 过期 Build 原子失败收敛

日期：2026-10-04；状态：`RAG_EMBEDDING_BUILD_RECONCILIATION_PASS`；当前 Phase：Phase 2 Platform Core。下一项：`RAG-03-A04-P01` Batch 网络前发送栅栏与当前授权重验。

## Changed

1. 过期RUNNING RAG Job不再由通用claim或RAG再claim终结，避免Job与Build/Index状态分裂。
2. 新增专用Reconciler，按数据库时间锁定当前generation，同事务将Lease/Attempt/Job、Build/Index及Batch收敛并写SYSTEM Audit；Audit失败全回滚。
3. 未发送PENDING Batch收敛为CANCELLED/`RAG_BUILD_LEASE_EXPIRED`；数据库守卫预留RUNNING Batch收敛为UNKNOWN/`RAG_PROVIDER_OUTCOME_UNKNOWN`，但该正向路径须等A04发送栅栏后再做实际验证。

## Files / Migration / API

- Files：`reconcile_expired_build.py`、`expired_build_reconciliation_repository.py`、Schema0081、单元与Windows11/PG18验证。
- Migration：`20261004_0081`；无对账历史可降0080，已对账历史拒降。
- API：无变更。

## Tests / Result

| 检查 | 结果 |
|---|---|
| 后端全量 | 2384项通过，3项条件跳过 |
| PostgreSQL 18.6 | `RAG_03_A03_P03_EXPIRED_RECONCILIATION_PASS` |
| 原子性 | Audit失败时Job/Lease/Attempt/Build/Index/Batch全回滚；成功时一次收敛并写唯一SYSTEM Audit |
| 竞态/安全 | 通用claim和RAG claim均不拆分过期Job；旧Worker续租拒绝；已对账历史拒降 |
| wheel | 隔离25项PASS；SHA-256 `1df2985741d742aca64516b24f27eb4b868e7c84f1b5377533fe1a2a3357d70b` |

Result：PASS。本项零Provider I/O、零Secret和零客户数据外发。

## Known Issues / Next

RUNNING Batch→UNKNOWN只完成数据库/仓储设计，因A04尚未创建真实发送前栅栏，本项不将其报告为实际运行PASS。下一项实现每批当前租约+未撤销授权重验与发送前持久化RUNNING栅栏，仍先使用本地合成Adapter，不发送客户数据。
