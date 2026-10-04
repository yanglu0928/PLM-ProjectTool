# AI-04-A06-P03-P01-A02：Jobs PostgreSQL 当前 Claim 与 Outbox 绑定

- 日期：2026-10-03
- 结果：`WINDOWS11_POSTGRESQL18_PASS / NO_EXTERNAL_CALLS`
- 依据：CR-AI-015、DEC-723、Jobs Lease/Fencing基线

新增Jobs-owned PostgreSQL Repository。它先复用唯一 Lease Owner 锁定并验证RUNNING Job、ACTIVE且未过期Lease、未完成Attempt、当前worker/fencing/attempt；随后严格验证 `ai/AI_TASK_EXECUTE/PROJECT`、原actor/Project/Trace、1～10次上限、Task幂等根，以及只含 `ai_task_id/egress_authorization_ref/input_fingerprint` 的payload。最后要求唯一原始 `AI_TASK_QUEUED` Outbox与Task/Job/Project/Trace/幂等根精确一致。

Windows 11 / PostgreSQL 18.6隔离库验证真实PENDING→RUNNING claim、ACTIVE Lease/Attempt、完整Owner证明；错误worker、错误fencing、额外endpoint payload和Outbox Job漂移均拒绝，拒绝路径不修改RUNNING Job代次。首轮脚本使用旧数据库工厂直接池参数导致TypeError，finally已清理临时库；改用当前工厂入口后从新库完整重跑PASS。

定向8项、后端全量2164项PASS/3项既定跳过；开发wheel SHA-256 `fd96d52395a7e27fd228d90fcc197a3eed982704cbeb1b5472e0afc1caab46eb`。Changed：Jobs PostgreSQL Owner Repository与隔离验证。Migration/API/Dependencies：无。Compatibility：复用现有Job/Lease/Attempt/Outbox，无生产装配。Rollback：撤Repository，历史不变。Known Issues：尚未把Claim与AI Task/Prompt/Model/Egress元数据组合为完整Grant，也未读取正文、创建Invocation或调用Provider。Next：`AI-04-A06-P03-P01-A03`。
