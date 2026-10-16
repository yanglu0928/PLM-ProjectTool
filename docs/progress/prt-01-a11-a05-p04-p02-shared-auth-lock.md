# PRT-01-A11-A05-P04-P02：资格预览共享授权锁与剩余性能偏差

2026-10-08 / 状态：`SECURITY_REGRESSION_PASS_PERFORMANCE_PRECHECK_FAIL`。

编码前检查：P04-P01已证同项目20并发资格预览P95约1.5秒且授权SQL长时间等待；复核发现预览复用写策略`WORKFLOW_CHECKLIST_RECORD`并持有`FOR UPDATE`。CR-PRT-005先记录差异、角色/归档/撤权风险、迁移/回滚和验证计划后实施。本项只改Project授权策略/仓储锁型与Workflow预览调用，不改冻结公开API、Schema、依赖、数据或Checklist写权限。

新增仅预览使用的`WORKFLOW_CHECKLIST_PREVIEW`：PROJECT_MANAGER、活动项目、同事务Project/Member/Department `FOR SHARE`；写路径仍用旧策略和排他锁，其他读策略不变。隔离PG验证两笔同用户同项目预览事务可同时持锁，而成员撤权UPDATE在持锁期间等待并触发预期lock_timeout；SQL事件确认实际语句为`FOR SHARE`，122次累计约1.1秒，旧排他锁约88秒。20并发资格的每个响应仍200/强ETag/PROTOTYPE阶段，旧全NOT_REQUIRED真实HTTP/PG链通过。后端全量3245通过、3跳过、4795子例；未跑Server2025或Debian13。

非仪表化ASGI预检：默认池两项三轮P95中位约752.69/748.22ms；测试用全链路20+0池约696.74/683.13ms。改善明显但仍不达非AI GET P95≤500ms，不能标性能PASS，也不能直接修改生产连接池。测试是本机Windows11隔离PG18.6/pgvector/合成小文件，不是Uvicorn网络或发行账户。下一步定位剩余约77条SQL/请求与磁盘证明成本，补正式loopback及撤权后失败关闭，再决定最小优化；生产Prototype入口和Gate3保持关闭/未通过。

升级无需操作；回滚可恢复预览对原写策略的调用并移除新策略/共享锁分支，持久历史不变。回滚不是降低校验：不能移除真实Review/Trace/文件物理证明或写时重新验证。
