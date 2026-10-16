# AI-04 Schema0063：AITask Root 与不可变输入引用

日期：2026-10-02；父版本 `20261002_0062`；依据 Gate2 冻结 SC-01/02、DM-04及 DEC-698。仅实现 AI-04-A02-P01，非完整 AI-04 物理 Schema。

`plm.ai_tasks`：UUIDv7 Root、GLOBAL/PROJECT Scope 与 ProjectId、受控 TaskType、请求者、32字节输入指纹、Prompt/Output/Context 策略引用、Task/Suggestion 状态、人工接受目标引用、Job/Trace、错误/重试、乐观锁与 UTC 时间。Project/User/Job FK、Scope/状态/策略/接受形态/时间 CHECK、项目状态和请求者索引。数据库触发器保护身份、输入指纹、策略和创建时间不被改写；每次受控状态更新要求 lock_version 递增，终态不能复活，禁止删除/截断。

`plm.ai_task_input_refs`：UUIDv7、所属 Task、序号、Scope/ProjectId、Owner 类型与不可变版本 UUID；序号在 Task 内唯一。数据库触发器在插入时对照父 Task 的 Scope/ProjectId 并要求 Task 仍 QUEUED，禁止更新/删除/截断。多态版本实际存在性、Owner 白名单及提交时授权仍必须由后续 Application/Owner Port 验证，不能仅凭 UUID/外键推定有效。

本增量没有 Invocation、Context 或逐次外发授权快照表，也不建立当前 Attempt 指针；这些属连续 P02。没有公开 API/AI 外发，不把表存在解释成可调用能力。冻结原提交 `64cdf09` 不改，Schema 以增量演进。

迁移：0062→0063；空表可降0062并重升；一旦有 Task/输入历史，受控降级拒绝，向前修复或经备份恢复，不删除历史。正式生产库尚未迁移。验证：Win11隔离PG18空库升/降/重升、既有用户/项目历史库升级、Alembic drift=0、Scope/FK/同项目触发器、输入不可变、终态与锁版本、非空拒降 PASS。目标环境 Server2025/Debian、正式角色权限与性能未验。
