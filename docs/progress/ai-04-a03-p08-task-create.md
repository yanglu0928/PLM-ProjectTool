# AI-04-A03-P08：AITask 内部原子创建

- 日期：2026-10-03
- 结果：PASS（内部能力，Windows 11 / PostgreSQL 18.6 隔离验证）
- 依据：CR-AI-010～012、DEC-701～704、冻结 `AI_TASK_CREATE`

新增 `AITaskCreateService`、`EgressAuthorizationOwnerPort` 契约和 PostgreSQL 仓储。服务依次完成 License、Session/CSRF、Project Role、幂等保留、全组 Input Owner 解析和授权 Owner 快照校验；只有授权引用/项目/源集合指纹/有效期/状态/角色/上限全部一致才创建。

首次创建在一个数据库事务中写入 AITask、唯一 Job、Outbox、完整 InputRef、Egress Snapshot、Audit 和通用 Receipt。Receipt 只指向 Task，重放通过Schema0066不可变 `job_ref` 恢复原 Task+Job，不再调用 Input/Egress Owner。Job/Outbox payload 仅存引用与指纹，无Key、Secret、Prompt或正文。

验证：单元5项覆盖首次创建、精确重放、源集合不匹配、过期授权和非受控TaskType；Win11隔离PG18.6实际链证明七类记录同事务、同Key精确重放、改载荷冲突及Audit故障全回滚。后端2111运行/3跳过PASS；开发wheel SHA-256 `d7978d74ee11f263ed25bd45fb8386cc178bfce4b14e8dbd75052e4dc88e0129`。

边界：仓库仍没有 Egress Preview/Authorization 正式生产聚合，因此本服务未在组合根注入 Owner，未挂载公开HTTP，也没有任何真实外发。
