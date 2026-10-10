# AI Task 显式重试 generation 数据模型增量

日期：2026-10-03；WBS：`AI-04-A06-P08-P05-P01`；依据 CR-AI-018、DEC-758/759/762。

Schema0075 新增 AI owned 不可变表 `ai_task_retry_generations`，以 `new_ai_task_id` 为主键，保存 `source_ai_task_id`、`root_ai_task_id`、新旧 Job、实际重试人、USER Audit、generation 序号、源 Job 预期版本及新 Job 首版本。一次显式 Retry 必须保留旧 Task/Job/Invocation 终态，不允许原地复活。

数据库在插入时锁定并验证：源 Task/Job 同为 `FAILED`或`CANCELLED`；`FAILED` 只有 `retryable=true` 可重试，因 Provider 结果未知而标记不可重试的记录必须拒绝。新 Task/Job 必须为 `QUEUED/PENDING` 首版，没有 Invocation、错误或终态时间。Task 类型、输入指纹、Prompt/Schema/Context Policy、Prompt 版本、参数指纹、Content Plan、有序 Input refs 及 Egress 授权快照必须与直接源完全一致，仅允许新 Task/Job/Trace/实际请求人/捕获时间变化。

generation 根由第一代源 Task 确定，后续派生必须沿用根并且序号逐代增加；`root_ai_task_id + generation_no` 唯一，因此一条根链只能线性向前，不能用不同幂等键从同一失败源无限分叉。最大代数同时受数据库 1～10 边界与原 Egress `max_retry_attempts` 约束。USER Audit 必须为当前项目和实际重试人的 `AI_TASK_USER_RETRY_REQUESTED`，目标是新 Task，`target_version_id` 指向直接源 Task，状态为源终态→`QUEUED`。

该表拒绝 UPDATE/DELETE/TRUNCATE；历史数据不猜测回填，空表可降级，一旦存在血缘则拒绝物理降级，只允许向前修复或受控备份恢复。P01 只建立 Schema/ORM 安全边界；P02 负责当前授权、幂等、原子创建与冻结 Retry API Owner 接线。
