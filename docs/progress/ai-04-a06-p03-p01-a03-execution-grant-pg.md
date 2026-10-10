# AI-04-A06-P03-P01-A03：完整 Execution Grant PostgreSQL 投影

- 日期：2026-10-03
- 结果：`AI_04_A06_P03_P01_A03_EXECUTION_GRANT_PG_PASS / NO_EXTERNAL_CALLS`
- 依据：CR-AI-015、DEC-722～724、冻结 DM-04/API-03/Schema0064及0071增量

新增 AI-owned 无正文元数据投影与 Grant Issuer。Issuer 在同一短事务中先调用 Jobs Owner 证明当前 RUNNING Job、ACTIVE Lease/Attempt、worker/fencing和原始Outbox，再锁定QUEUED Task，验证顺序InputRef及来源摘要、当前ACTIVE Prompt版本与哈希、Schema/Context/参数摘要、AVAILABLE CHAT Model和不可变Egress快照；随后调用Egress Owner重验当前Provider/Config/Model路由、授权未撤销/未过期、批准载荷摘要、数据类别及全部上限。AI模块不直接读取裸Job表。

P02内部Grant补齐 `minimal_payload_policy_ref` 和 `max_record_count`：两者来自当前Authorization Owner，完整Authorization摘要必须与Task快照一致。License在短事务内及事务边界后各检查一次；未来网络发送边界仍须再次检查。Grant、Job/Outbox和普通日志均不包含Prompt正文、输入正文、Key、endpoint或响应；本项不创建Invocation、不调用Provider。

Windows 11/PostgreSQL 18.6隔离实库从完整Provider/Model/Prompt/Egress/Task/Job/Outbox链签发唯一有效Grant；Task创建后Prompt活动版本切换、快照模型漂移、批准payload摘要漂移及授权撤销均拒绝，`ai_invocations=0`。首次脚本因未在Authorization同事务写Audit/首次结果被延迟历史约束拒绝；补成原子授权链后重跑。第二次试图直接创建引用非当前Prompt的Task被数据库守卫拒绝，改为先按当前版本创建、再切换活动版本，最终从全新库通过。

定向15项、后端全量2167项PASS/3项既定跳过；开发wheel SHA-256 `87690d1d519bfd23bc0b8ca0e02881f989e67d07d66227a623c3bdc00215b16d`。Changed：内部Grant字段、Issuer、AI PostgreSQL Repository、单元及隔离验证和追溯文档。Migration/API/Dependencies：无。Compatibility：未接生产Worker，不改变公开行为。Upgrade：无数据迁移。Rollback：撤未装配Issuer/Repository并保留Task/Job/授权历史。Known Issues：内容Owner、Prompt确定性渲染、服务端Envelope、Preview重构、Invocation、Adapter和结果发布尚未实现；Server 2025未复验，Debian 13按用户要求暂跳过，Gate 3/UAT/可用包未完成。Next：`AI-04-A06-P03-P02-P01` 内容Owner与确定性Envelope编码前核查。
