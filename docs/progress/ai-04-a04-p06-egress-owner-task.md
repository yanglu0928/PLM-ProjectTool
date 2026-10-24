# AI-04-A04-P06：EgressAuthorization Owner 当前有效投影与 AITask 接入

- 日期：2026-10-03
- 结果：PASS（Windows 11 / PostgreSQL 18.6 隔离验证）
- 依据：CR-AI-010～013、DEC-703/705/710/711、冻结 `AI_TASK_CREATE`

新增 EgressAuthorization Owner 应用投影、可注入的 AITask→Purpose 受信映射和 PostgreSQL 当前事实仓储。Owner 在 AITask 创建事务内锁定 Authorization Root，要求 `AUTHORIZED@0`、同PROJECT、`AI_TASK` operation、未过期、完全相同的 SourceRef 集合指纹和受信Purpose，并在SQL中同时要求当前 ACTIVE Provider、当前 Config 与 AVAILABLE Model。任一条件失配均以 `AI_EGRESS_AUTHORIZATION_INVALID` 失败关闭。

Owner 将权威根投影为既有 `AuthorizedEgressSnapshot`，将批准角色映射为冻结的大写枚举，并对包含 Authorization/Preview/Provider/Model/边界/指纹/批准事实/状态的完整视图计算规范化 SHA-256 指纹。AITask 继续在同一事务写 Task、Job、Outbox、InputRef、Authorization Snapshot、Audit 和 Receipt。新 Key 不得使用已撤销/过期授权；已成功的同 Key Task 只重放原 Task/Job，不新建外发工作。

验证：定向14项 PASS；Win11 隔离 PG18.6 真实验证当前 Owner 投影、Purpose/Source/过期/撤销/Project 拒绝、Task七类记录原子落库和历史 Task/Job 重放 PASS；后端2125运行/3跳过 PASS。验证脚本首轮使用了早于数据库 `approved_at` 的合成时钟，第二轮沿用了错误 Job 表前缀；两次都只修正夹具并重跑完整链路，未放宽生产规则。开发 wheel SHA-256 `ad6e4a017f425c8a58bf6fc1643add7bf2a70c87998869548ae9a360f5ce687c`。

边界：本项不新增 Schema、HTTP 或真实外发。Purpose 映射只定义受信注入机制，正式部署值、Worker 每次发送前重验、公开入口和生产组合待后续；Gate 3/UAT/可使用程序包仍未通过。
