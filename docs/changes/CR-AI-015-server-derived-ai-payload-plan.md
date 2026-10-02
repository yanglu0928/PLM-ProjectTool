# CR-AI-015：AI 最终载荷必须由服务端确定性构建并与外发授权逐字节绑定

日期：2026-10-03；状态：依 V1.1 持续授权登记，实施中；关联冻结 ADR-004、DM-04、API-03、Schema0064、CR-AI-012～014；原 Gate 2 冻结提交 `64cdf09` 不改。WBS `AI-04-A06`。

## 冲突与证据

冻结基线要求每次外部 AI 调用保存实际 Provider/Model/Prompt/Input/Context、请求载荷摘要、逐次外发授权和 Invocation，并要求实际 payload、Provider/config、Model/revision、Prompt、Context 或 source version 变化时重新授权。当前 P05 执行前置可以重验 Task/Job/Prompt引用和当前 Egress Authorization，但尚未构建最终 Prompt/输入正文，也未创建 Invocation；现有 Egress Preview 的 `payload_fingerprint` 由 HTTP 客户端提交。客户端没有权限取得完整 Prompt 正文，也不能可靠复刻服务端模板、编码、Provider载荷序列化和Token计算，因此该摘要不能单独证明“获批载荷就是实际发送载荷”。直接接 Worker 会形成批准对象与发送字节不一致的安全缺口。

现有 Schema0064 已提供 AIInvocation、ContextRef、外发授权快照、请求/响应摘要、用量、错误和终态约束，但 P05 投影尚未携带完整授权上限、Prompt模板内容/哈希、schema version、model revision、精确 InputRef 和实际载荷计划。仓库也没有生产 AIService/ModelRouter/ProviderAdapter、确定性模板渲染、服务端Token估算、Invocation开始/终止或Suggestion正文 Owner。上述缺项不得以客户端摘要、Job payload、普通日志或直接访问 Document 内部表代替。

## 方案比较与决定

- A：先发送，再以实际响应回填摘要。否决；越限或未获批载荷已经外发，无法回滚。
- B：用 Task/Input/Prompt 引用的逻辑摘要代替实际请求字节摘要。否决；模板、正文、编码、Provider序列化或Context变化不会被逐字节捕获。
- C：由服务端在外发前确定性构建 provider-neutral `AIExecutionEnvelope`，计算规范化请求摘要、实际字节与保守Token上界；AI_TASK 类型的 Egress Preview 改由同一构建器派生，Task创建和每次Invocation再次构建并要求与授权摘要、来源、Provider/config/model/region、数据类别及上限完全一致。选择C。

## 最小实施序列

1. P02 定义不含正文的 `AITaskExecutionGrant` 与严格载荷/上下文计划合同，补齐P05投影遗漏的授权上限、Prompt/Model版本、InputRef及快照身份；仅内部代码和测试。
2. P03 建立各资源 Owner 的受权内容投影、确定性Prompt渲染与有界 `AIExecutionEnvelope`；正文仅存在于短生命周期内存对象，不进Job/Outbox/普通日志。
3. P04 将 AI_TASK Egress Preview 接到同一服务端构建器；生产组合拒绝客户端自报的AI payload摘要。保持原路径，必要的请求增量单独更新API文档并兼容非AI操作。
4. P05 在同一短事务创建下一PENDING Invocation并绑定精确授权快照/Context，提交后才允许网络I/O；并发、attempt上限和Job fencing失败关闭。
5. P06 实现 `AIService → ModelRouter → ProviderAdapter` 的有界调用与Secret最小读取；发送前最后一次授权/Lease检查，不持有数据库事务跨网络。
6. P07/P08 分别实现成功Schema校验/Suggestion受权存储与失败/未知结果发布、取消和安全重试；最后做无外发合成、明确授权真实调用、质量回归和平台验收。

## P02实施结果与P03细分

P02已实现无正文 `AITaskExecutionGrant`、覆盖全部执行元数据的规范化Grant摘要以及 `AITaskPayloadPlanProof` 准入。Task/Job/Attempt、来源、批准payload、记录/字节/Token上限或有效期任一变化均拒绝；敏感摘要字段不进入对象repr。定向4项、后端2161运行/3跳过及wheel通过，无Schema/API/依赖/外发。

为保持 Jobs Owner 边界且不让AI模块直接把裸Job行当授权，原P03细分：P03-P01先实现Jobs当前Lease/Attempt专属证明与PostgreSQL Grant元数据投影；P03-P02再实现内容Owner和确定性Envelope。该细分不改变原Scope，不新增外发或跳过Preview重构。

P03-P01-A01已完成Jobs-owned当前Claim内部合同，固定原actor/Project/Task/Authorization/Input摘要/Trace与attempt/fencing/max-attempts，并在调用方短事务内失败关闭；定向7、后端2164运行/3跳过及wheel通过。当前只是Owner合同，尚无PostgreSQL实现，不标实际Claim/Grant PASS。A02继续核ACTIVE Lease/Attempt、RUNNING Job、原Outbox和payload绑定。

## 影响、迁移与回滚

该变更补充冻结实现顺序，不修改原冻结提交。P01无代码、Schema、依赖或公开API变化。后续若需新增数据库对象或请求字段，必须在相应切片先给出ORM/Migration、空库/有数据up/down、兼容与API增量证据。已存在的Egress Preview/Authorization和Task历史保留；不能证明服务端载荷计划的旧记录一律不可执行，不猜测回填。

回滚优先撤销新Worker/Router组合并恢复AI执行404/不消费队列，保留Task、Authorization、Invocation和Audit历史；产生Invocation历史后不物理删除或倒写。Provider网络调用一旦发生不能宣称回滚外发，故任何真实调用都必须在发送前完成所有校验并另有明确数据范围授权。

## 验证计划与剩余风险

每个切片至少覆盖 unit、PostgreSQL并发/回滚、Project隔离、授权撤销/过期、Provider/Prompt版本漂移、payload一字节变化、字节/Token/重试上限、Job lease/fencing、Schema INVALID、超时未知结果、日志与错误脱敏。真实 Provider 调用和客户数据外发不由本CR默认授权；使用合成内容完成协议验证后，再按用户明确的数据范围授权执行真实质量复验。

风险仍包括不同Provider的Token算法、模板转义、内容流读取期间撤权、调用超时后的远端未知结果和Suggestion正文保留。控制为Provider Adapter专属估算/硬上限、严格模板语法、读取前后双重Owner校验、逐次Invocation和未知结果状态，不以“发送成功”推断业务成功。
