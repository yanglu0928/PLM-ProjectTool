# AI-04-A05-P03：Task Policy、Prompt Owner 与完整提交快照

- 日期：2026-10-03
- 结果：PASS（内部应用/基础设施与Win11 PostgreSQL 18.6真实链）
- 依据：CR-AI-014、DEC-715～717、Schema0070

新增不可变版本化 `AITaskSubmissionPolicyRegistry`：每条策略显式绑定policy reference/version、task type、PromptTemplate、purpose、Output Schema、RAG/context policy及最多16个严格标量参数字段。参数仅支持有界 `STRING/INTEGER/BOOLEAN`，强制必填、枚举、长度或数值范围，拒绝未知键、错误类型、空白污染和超过16,384 UTF-8字节的JSON；Document/Requirement正文仍只能走InputRef。

新增 `AITaskPromptOwner` 与 PostgreSQL 当前版本仓储。创建事务在收到新幂等请求后锁定DEPLOYMENT/ACTIVE PromptTemplate及其活动版本，重核task type、Output Schema和RAG Policy；参数先由应用严格校验，再由PostgreSQL转为JSONB并以数据库规范文本计算SHA-256。完整Prompt/参数快照随Task/Job/Outbox/Input/Egress/Audit/Receipt原子写入，Task Policy purpose必须与当前Egress Authorization一致。历史幂等重放直接返回已落库Task，不受后续Prompt退役影响；Prompt退役只阻止新Task。

Windows 11 / PostgreSQL 18.6随机新库验证严格参数、ACTIVE Prompt锁定、数据库JSONB摘要、完整Task快照、原子链、同Key历史重放，以及参数/用途/Schema不匹配和Prompt退役失败关闭。首轮真实链发现SQLAlchemy把JSON文本再次编码为JSON string，数据库约束正确拒绝；改为Text绑定后显式转JSONB并从新库完整重跑通过。新增及相关定向16项PASS，后端全量2140项PASS、3项既定跳过；wheel SHA-256 `c214a8a277f9ef8521b68a62930b389053d105891c87bf68b4963fb2c1c215a8`。

Changed：Task创建命令/服务/持久请求、版本化Task Policy、Prompt Owner及仓储、Task仓储完整0070写入、单元与PG验证。Compatibility：内部尚未公开的创建合同增加 `task_parameters` 与两项强制依赖；无Schema0071、公开API、依赖或Provider外发变化。Upgrade/Rollback：须先升0070；停止后续组合可回退应用，但已创建的完整Task历史保留且0070不可物理降级。Known Issues：公开POST/GET、部署Task Policy来源与Windows组合、旧NULL Task执行拒绝、Worker发送前撤销/payload重验、正式信任、Server2025、Gate3/UAT/交付包待完成。Next：`AI-04-A05-P04` AI Task创建HTTP合同。
