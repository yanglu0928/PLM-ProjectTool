# AI-04 Schema0064：Invocation、Context 与逐次外发授权快照

日期：2026-10-02；父版本 `20261002_0063`；依据 Gate 2 冻结 SC-01/02、DM-04、API-03及 DEC-698/699。

|对象|关键字段|边界与约束|
|---|---|---|
|`plm.ai_egress_authorization_snapshots`|Task/Scope/Project、授权引用、用途、Provider/Config、区域、允许数据类别、审批人、授权时间窗与SHA-256|逐次不可变；同Task Scope/Project；类别为非空、唯一、有界字符串；区域与Config一致；不复制SecretRef、Key或客户正文|
|`plm.ai_invocations`|Task/Attempt、Provider/Config/Model/Revision、PromptVersion、Schema、输入/请求/响应/Context指纹、载荷引用、外发模式、状态/用量/时延/错误|同Task Attempt连续唯一；仅ACTIVE Provider、AVAILABLE Model与当前ACTIVE Prompt可建新PENDING Attempt；外部Provider必须引用有效同Task授权快照；终态不可变，结构化成功必须Schema VALID|
|`plm.ai_invocation_context_refs`|Invocation、顺序、Scope/Project、Owner/Object/Version、内容指纹|仅PENDING Attempt可追加；同Invocation Scope/Project；追加后不可改删/截断|
|`plm.ai_tasks.current_invocation_ref`|当前Attempt引用|复合外键限定同Task；更新时必须指向最新Attempt并推进Task锁版本，不得清空已建立指针|

升级只新增三张表和Task可空指针，不修改冻结 `/api/v1`。空新增表且无当前指针时可降回0063；一旦产生授权/Invocation/Context历史即拒绝物理降级，须向前修复或从受控备份恢复。0064不开放AI调用，也不证明正式外发授权、Provider信任或Gate 3通过。
