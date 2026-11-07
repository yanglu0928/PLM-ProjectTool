# OUT-01-A01-P28 Output 活动租约证明结果

- 日期：2026-11-05
- Change Request：CR-OUT-024
- 结论：PASS_SCOPE_LIMITED
- Hosted run：[41944746044](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41944746044)
- 环境：GitHub hosted Windows Server 2025，D盘临时目录和合成PG18；未在本机/C盘运行。

## 结果

新增 Jobs Owner 的Output专属只读活动租约proof。PG verifier实际通过 Output-specific claim 取得Output Generate job，再核对Owner/类型、当前worker、fencing token、attempt、数据库时间及Job/Lease到期一致性。

PG smoke摘要：active_output_claim_proof=true；wrong_worker_denied=true；stale_fencing_token_denied=true；other_owner_denied=true；expired_lease_denied=true；job_state_mutated_by_proof=false。未执行插件、未生成文件、无外部调用/客户数据，Schema未变化。

全量后端4,031 tests/wheel、前端/build、PG18/pgvector、父包组装及父包PG smoke成功；A35成功，P25仍在initdb阶段0xC0000135失败。其余A17/A34仍在run收尾中，不能据此声称整条workflow全部成功。

## 边界

Proof只在短事务读取时有效，不会续租，也不保证事务后的租约持续有效；未来副作用前仍需重新验证当前fencing并通过Jobs事务完成状态推进。无Schema/API/Migration变化，不代表Worker执行或文件发布。
