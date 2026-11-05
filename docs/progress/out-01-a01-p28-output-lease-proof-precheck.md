# OUT-01-A01-P28 编码前检查：Output 活动租约 proof

- 日期：2026-11-05
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P28
- 结果：PASS_WITH_LIMITATION，可开始编码
- Change Request：CR-OUT-024

## 检查结论

- 已核对 Jobs Repository：内部 _current 会锁定Job/Lease/Attempt并验证RUNNING、当前token、worker_ref与未完成Attempt；heartbeat会按PostgreSQL statement_timestamp校验未过期后续约。专属claim仅锁定 output/OUTPUT_GENERATE。
- 缺口：Output没有专属只读方法来证明Claim在当前DB时点仍属于其Output Job Owner；_current不单独校验owner/job_type，通用接口不适合作为Output worker的安全证明合同。
- 实施目标是Jobs层专属check_output_claim：重用现有锁和fencing查询，额外校验owner/type、expires_at一致性、DB时钟未过期和attempt序号；只读，不刷新租约/改状态。
- 输入来自P26的claim_next_output；验证拒绝伪造或不完整claim。输出仍为短期 proof，不授权事务外副作用。
- 不修改ORM/Migration/API、Output状态、默认组合；无Worker/plugin执行/文件发布。
- 测试：unittest定向用例；D盘hosted PG真实lease、错误worker/token和Owner错配；后端全量及父包PG smoke。用户本机/C盘不运行。
- 前置/回滚/隐私/验证已记录于CR-OUT-024；允许编码，结论仅限租约证明。
