# CR-OUT-026：Output 不可恢复生成失败的原子终态收敛

- 日期：2026-11-05
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P30
- 来源：P29 已证明 Output 可在活动 lease 下进入 GENERATING；当前尚无失败终态事务将 Output 与 Job 一并收敛
- 状态：编码前检查 PASS_WITH_LIMITATION；候选只覆盖受控 worker 报告的不可重试失败，不执行插件/渲染/文件写入
- 基线：冻结 OutputRequest 状态/Jobs lease/Audit；不改 Schema、Migration、API、默认组合

## 决策

在一个共享 UnitOfWork 内，先锁定并校验精确绑定的 OutputRequest，再以当前 fencing token/worker 核验 Output Job lease。只允许将与 claim、project、snapshot、job 及 deterministic execution ref 完全匹配的 GENERATING 请求置为 FAILED；调用 Jobs Owner 的 retry_or_fail(retryable=false) 结束当前 attempt 并置 Job FAILED；Output 记录 completed_at/lock_version，并追加不含错误详情的 SYSTEM Audit。错误仅接受代码白名单，不保存 worker 传入的任意文本、文件名或堆栈。

这不是插件执行工作，也不表示重试、输出内容校验、文件发布或正式服务账户已完成。P30 用于失败关闭状态一致性。

## 方案与边界

- 将 Output 标 FAILED 而不收敛 Job：会留下仍 RUNNING 的 Job，不采用。
- 让 Output Owner 自行更新 Jobs ORM：破坏模块 Owner 边界，不采用。
- 复用 Jobs retry_or_fail 同一事务，并由 Output repository 独立更新已锁行：保留 Jobs/Output 各自 Owner，选用该方案。
- 固定允许代码；不接受自由文本；不允许 worker 决定是否可重试，本项只处理不可重试类别。
- 与取消路径一致采用 Output→Jobs 锁顺序，避免死锁。Audit 失败必须全回滚。

## 风险、回滚和验收

- 风险：worker 身份/服务账户仍未正式装配；P30 只通过内部组合注入 system actor，不将其当生产信任。
- 回滚：移除Owner、Repository、测试/验证器及 smoke hook；无数据迁移。
- 验收：单元正负用例；同一PG18 transaction真实验活动lease、绑定/错worker/stale token拒绝、Job与Output同时FAILED、单条SYSTEM Audit、Audit异常两侧全回滚；后端全量测试/wheel、前端/build、父包PG smoke及A17/A34/A35/A50 hosted回归。
- 限制：无插件/外部API/文件输出/客户数据；仅GitHub hosted Windows Server 2025 D盘RUNNER_TEMP。P25 0xC0000135仍独立未通过，不能借P30结果宣称P25/Pilot/Gate/Release通过。


## 首轮 hosted 验收偏差（2026-11-05，修正前登记）

- Run [41958856962](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41958856962) 后端4042项测试中仅新增的 P30 正向单测失败，另外5项P30边界单测通过；失败发生在AuditEventDraft校验，未调用真实数据库且 fake UOW已回滚。首轮实现把Audit outcome使用为 `FAILURE`，而仓库冻结Audit合同仅接受 `SUCCESS`、`DENIED`、`FAILED`。
- 修复计划：仅将P30 Audit outcome改成冻结合同中的 `FAILED`，并同步单位/PG验收期望值；不放宽Audit校验、不改合同或生产逻辑。随后重新执行后端全量测试、wheel、同父包PG smoke及云端全链。P30和P25均不得在未通过前标记PASS。
