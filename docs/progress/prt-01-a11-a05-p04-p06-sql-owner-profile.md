# PRT-01-A11-A05-P04-P06：资格读取SQL归类诊断

2026-10-08 / 状态：`DIAGNOSTIC_COMPLETE_PERFORMANCE_PRECHECK_FAIL`。

编码前检查：Phase 2；前置P04-P05已测文件证明非主要网络瓶颈，性能目标仍为20并发非AI GET P95≤500ms；本项只扩展隔离验证脚本的SQL语句首表前缀统计，不改生产代码、API、Schema、权限或数据。CR-PRT-005记录风险与后续方案；关闭SQL计时器的网络值才可用于性能比较。

Windows11隔离PG18.6/pgvector、同一批准Requirement/Prototype、真实Review/Trace/Document/Link夹具，122次资格请求（两项各预热一次+各三轮20并发）共7686条SQL，63条/请求。按首个`FROM plm.<table>`粗分：`rvw`2196（18/请求）、`req`1952（16/请求）、`prt`1708（14/请求），合计5856条，约76.2%；`evd`610、`prj`366、`auth/wfl/doc`各244、`cap`122。默认池与测试用20+0池计数一致，脚本退出0。该归类并非精确调用图或独立性能贡献，并发SQL耗时和不能直接除以端到端P95。

代码核对：Review `get_round`读取Review根、所有Round、目标Round及Assignment/Decision/Snapshot/Ref/SubjectLock/Event六类当前事实；本夹具两种受审主体各一轮，18条Review查询/请求有业务来源。跨请求缓存、删除任何完整性检查或放宽目标均不可接受。下一独立P07仅设计同事务批量读取并验证锁序、类型、状态/事件数量及篡改拒绝；若无法安全减少往返，保留性能FAIL并转不依赖任务。无迁移；撤诊断统计即可回滚，历史不变。生产Prototype入口、Gate3与可用包仍未通过。
