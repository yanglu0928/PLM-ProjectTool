# AI-04-A05-P01：AI Task 创建/读取公开合同前置核查

- 日期：2026-10-03
- 结果：PASS（前置核查与差异登记；未开放API）
- 依据：冻结 API-03、DM-04、Schema0063～0069、CR-AI-010～013

静态核对确认内部 `AITaskCreateService` 已具备License、Session/CSRF、Project角色、幂等、Input Owner、当前Egress Authorization Owner、Task/Job/Outbox/Input/Snapshot/Audit/Receipt同事务写入，并只返回 TaskRef+JobRef；但仓库不存在AI Task公开Router或读取服务。

发现阻止直接挂载的两项实质缺口：一是提交仅保存三个语法受限策略字符串，未锁定活动PromptTemplate/PromptVersion及其task type/output schema/RAG policy一致性；二是冻结合同允许的“最小业务参数”在DTO、Schema和持久层均不存在。直接把任意JSON放入Job会形成未授权正文旁路，延迟到Worker解析Prompt又会造成提交/执行版本漂移。

已登记 `CR-AI-014`，选择先以Schema0070增加不可变Prompt版本和严格最小参数快照，遗留NULL历史只读保留并禁止执行；再由非敏感版本化Task Policy限定task type、Prompt、purpose、参数Schema，之后才开放创建HTTP与读取链。此选择不修改原冻结提交，不新增厂商调用或外发。

Changed：仅文档/决策/状态；无程序、Schema、API或依赖变化。Tests：静态对照冻结API/数据模型、现有应用服务、ORM/Repository、Project授权和Egress Owner；未执行新运行测试，P09的后端2136运行/3跳过证据保持不变。Known Issues：0070、Task Policy/Prompt Owner、HTTP/读取、Worker发送前撤销与payload重验、正式信任、Server2025、Gate3/UAT/交付包待完成。Next：`AI-04-A05-P02` 实现Schema0070 ORM/Migration与Windows 11/PostgreSQL 18迁移验证。
