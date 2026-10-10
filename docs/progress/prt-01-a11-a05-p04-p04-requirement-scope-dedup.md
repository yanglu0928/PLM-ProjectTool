# PRT-01-A11-A05-P04-P04：Requirement完整范围扫描去重

2026-10-08 / 状态：`REGRESSION_PASS_PERFORMANCE_PRECHECK_FAIL`。

编码前检查：P04-P03网络20并发资格功能正确但P95约710/714ms，高于500ms目标；SQL诊断和代码核对发现Prototype Owner与其调用的Requirement Owner在同一事务内各做一次完整范围锁定。CR-PRT-005先记录方案、安全/性能风险、迁移/回滚及验收后实施。本项只调整两个Owner的内部Port与装配；冻结公开API、Schema、业务规则、权限、文件校验和生产开关不变。

Requirement Owner现一次锁定完整范围并完成原当前版本/来源Evidence/Review资格证明，内部返回同事务的`(locked_scope, qualification)`；其原独立资格接口只投影qualification，外部行为不变。Prototype Owner不再单独访问Requirement仓储，仍校验返回锁与资格的项目、阶段、主体和版本一致性。测试对同一Owner的组合方法只调用一次仓储锁定。

Windows11隔离PG18.6/pgvector、真实批准Requirement/Prototype/Review/Trace/Document文件/Link下，SQL计时的122次资格请求从9394降至7686条，约77→63条/请求。非仪表化Uvicorn loopback三轮20并发P95中位约594.00/632.23ms，所有响应200、强ETag与阶段正确，但仍不达500ms。混合范围缺决定/文件漂移/双重认领、部分Coverage/ILLUSTRATES、跨项目/撤权、多原型重复与互补并集等隔离PG/HTTP负例顺序回归退出0。后端全量3246通过、3跳过、4795子例；Server2025未运行，Debian13按用户指令跳过。

无数据库/配置迁移；若需回滚，恢复Prototype单独范围扫描及原Owner调用，保留历史。生产Prototype入口、Gate3与交付包仍不得标PASS。下一项继续定位约63条SQL/请求与磁盘完整性证明成本，并做不削弱证明的局部优化与正式网络复验。
