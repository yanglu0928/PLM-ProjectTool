# RAG-03-A03-P02 受权 Build 创建、claim 与原子启动

日期：2026-10-04；状态：`RAG_EMBEDDING_BUILD_BEGIN_PASS`；当前 Phase：Phase 2 Platform Core。下一项：`RAG-03-A03-P03` 单次租约过期后 Job/Build/Index 失败收敛。

## Changed

1. 新增 `RAGEmbeddingBuildPlanner`，以固定Index和逐批Authorization创建唯一Job/Build/Batch计划；批次顺序、来源范围和授权引用先在应用层封闭，数据库在提交时再验证完整计划。
2. 新增 Jobs-owned `RAGIndexBuildClaim`及PostgreSQL仓储，只允许`rag/RAG_INDEX_BUILD`、generation=1、max_attempts=attempt=fencing_token=1和精确payload/idempotency/scope/project/actor/trace。
3. Schema0080替换Index/Build守卫：只开放持有当前租约的`PLANNED→RUNNING/BUILDING`，通过deferred trigger要求双状态同事务完成。
4. 向量记录必须对应精确来源范围且Batch已SUCCEEDED；当前Batch转换仍封闭，所以P02无向量写入路径。

## Files / Migration / API

- Files：`modules/rag/application/embedding_build_plan.py`、`embedding_build_begin.py`，对应PostgreSQL仓储，Jobs claim合同/仓储，单元测试和实库验证脚本。
- Migration：`20261004_0080`。未启动且无向量历史可降至0079；已启动历史拒绝物理降级。
- API：无变更；冻结`/api/v1`未破坏。

## Tests / Result

| 检查 | 结果 |
|---|---|
| 后端全量 | 2378项通过，3项条件跳过 |
| PostgreSQL 18.6 | `RAG_03_A03_P02_BUILD_BEGIN_PASS` |
| Migration / drift | 0078历史库升级至0080，`command.check`无新操作；已启动历史拒降 |
| 正向 | 双批独立授权计划、RAG专用claim、Build RUNNING + Index BUILDING原子提交 |
| 负例 | Parser/AI Owner隔离；PENDING Batch向量写入、未开放Batch转换和已启动降级均拒绝 |
| wheel | 隔离22项PASS；SHA-256 `cdeeb0404194cd6c2c00d013e48d6d1477b2c797411e6eef4554be31ace30056` |

Result：PASS。本项只使用合成数据和一次性数据库，无Provider I/O、Secret或客户数据外发。

## Known Issues / Next

租约过期时Jobs层会将单次Job收敛为FAILED，但Build/Index尚需由RAG Owner原子收敛；因此P03先完成过期/失败对账，不在本项提前开放Batch网络发送。Embedding Adapter、发送栅栏、READY/ACTIVE、性能、Server2025/Debian13、Gate3/UAT和正式发行包均未由本项证明。
