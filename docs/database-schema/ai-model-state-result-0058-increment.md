# AIModel 安全状态首次结果：Schema 0058 增量

日期：2026-10-02；WBS：`AI-02-A08-P01`；依据 CR-AI-004/005、DEC-670、冻结 DM-04/API-03。原 Gate 2 冻结版本与提交 `64cdf09` 保留。

`plm.ai_model_state_results` 是 AI 自有不可变首次响应结果，不存厂商 Key、Prompt 或客户正文。主键 `state_result_id`；外键分别绑定 `ai_models`、`auth_users`、`aud_events`；保存 `trace_id`、`operation`、`before_state`、`result_state`、`expected_lock_version`、`lock_version`、`accepted_at` 与 `created_xid`。`(ai_model_id,lock_version)`、`audit_event_id` 唯一，防止同版本/同审计重复结果。

Check 只接纳 `SUSPEND: AVAILABLE→SUSPENDED` 或 `RETIRE: AVAILABLE/SUSPENDED→RETIRED`，要求版本加一、非零身份及有效时间。UPDATE/DELETE/TRUNCATE 触发器保护历史。当前不表示 AVAILABLE、质量通过或厂商调用资格。

Migration `20261002_0058`：空库 up/down/re-up 与有 Model 历史升级已在 Windows11 隔离 PG18.6 验证；非空结果表拒绝物理 down，正式生产升级未运行。Alembic ORM drift=0。后续 P02 必须保证模型状态变更、结果、Audit、幂等收据同事务；仅靠本表不能证明应用层授权与实际转移一致。
