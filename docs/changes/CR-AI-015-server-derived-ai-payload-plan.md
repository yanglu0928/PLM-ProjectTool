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

P03-P01-A02已实现Jobs PostgreSQL Owner：复用当前Lease锁，证明RUNNING Job、ACTIVE Lease、未完成Attempt、worker/fencing、严格AI payload和唯一原始Outbox。Win11/PG18.6正负链、定向8、后端2164运行/3跳过及wheel通过。首轮验证脚本旧工厂参数已修正并从新库重跑。A03继续组合AI-owned Task/Input/Prompt/Model/Egress元数据；本项仍无正文/Invocation/外发。

P03-P01-A03已实现完整无正文Grant投影：同一短事务先取Jobs-owned Claim，再锁定AI Task并核顺序InputRef、当前Prompt、Schema/参数、AVAILABLE CHAT Model和不可变Egress快照，最后由Egress Owner重验当前授权/路由/上限；AI侧不直读裸Job。P02内部Grant补齐最小载荷策略和最大记录数，由当前授权投影提供且受Task快照中的完整授权摘要约束。Win11/PG18.6有效链签发，Prompt活动版本漂移、模型/批准payload快照漂移及撤销拒绝，定向15、后端2167运行/3跳过、wheel通过；无Invocation/外发。验证夹具两次先后被授权历史完整性与Task当前Prompt守卫正确拒绝，均修正夹具后从新库重跑。P03-P02继续内容Owner和确定性Envelope。

P03-P02-P01静态核查进一步确认：业务 `DocumentVersion` 不能唯一决定实际解析正文，Document Owner读取正文必须指定精确 `ParseRecord`，而当前Preview/Authorization/Task没有持久化ParseResult、编码与Estimator身份；仓库亦尚无RAG Context生产实现。已另登记CR-AI-016，选择Preview阶段生成不可变 `AIExecutionContentPlan` 并让Authorization/Task/Invocation绑定，旧无Plan历史不可执行；P03-P02先实现未装配合同与Owner，P04再实施兼容Schema/API增量。本结论不修改本CR的服务端确定性Envelope方向。

P05-P01静态核查确认Schema0064已有Invocation/Context/Task当前指针与状态机，但仓库没有业务Invocation写入器、AI Task Worker、ModelRouter或ProviderAdapter；现有AI_PROVIDER_WORKER仅用于合成Provider探针。Schema0072为Invocation增加了PlanRef外键和更新不可变守卫，却未扩展0064插入守卫以核Task/授权快照/Plan同源。决定先以P05-P02追加0073新写完整性守卫，再实现短事务Invocation Begin；旧NULL历史不回填、不执行。本项仅文档，无代码、Schema、API、依赖或外发。

P05-P02已新增Schema0073独立INSERT守卫：新Invocation必须是AUTHORIZED、非空PlanRef，并与Task、授权快照和Content Plan的静态身份、策略、Prompt/Schema、Context、Provider/Model/revision及payload证明一致。旧NULL历史保留，但升级后新NULL/跨Plan/payload漂移失败关闭；有新Plan绑定Invocation时拒绝降级。Win11/PG18.6空库/历史库升降重升、drift和负例通过，后端2211运行/3跳过及wheel通过。无公开API、依赖、运行装配或网络外发；P05-P03继续短事务Begin。

P05-P03已新增无正文Invocation Begin服务与PostgreSQL Repository：Grant在调用方UoW内签发，下一PENDING Attempt、Task当前指针/状态/开始时间/锁版本同事务提交，提交后再检License。Win11/PG18.6真实UoW证明单次原子写、重复拒绝及注入故障全回滚；定向9、后端2213运行/3跳过及wheel通过。首次验证发现UoW需显式commit，修正后新库完整重跑。无公开API/迁移/依赖/Worker装配/外发；P05-P04继续真实Claim→Envelope→Begin组合和发送前Proof。

## 影响、迁移与回滚

该变更补充冻结实现顺序，不修改原冻结提交。P01无代码、Schema、依赖或公开API变化。后续若需新增数据库对象或请求字段，必须在相应切片先给出ORM/Migration、空库/有数据up/down、兼容与API增量证据。已存在的Egress Preview/Authorization和Task历史保留；不能证明服务端载荷计划的旧记录一律不可执行，不猜测回填。

回滚优先撤销新Worker/Router组合并恢复AI执行404/不消费队列，保留Task、Authorization、Invocation和Audit历史；产生Invocation历史后不物理删除或倒写。Provider网络调用一旦发生不能宣称回滚外发，故任何真实调用都必须在发送前完成所有校验并另有明确数据范围授权。

## 验证计划与剩余风险

每个切片至少覆盖 unit、PostgreSQL并发/回滚、Project隔离、授权撤销/过期、Provider/Prompt版本漂移、payload一字节变化、字节/Token/重试上限、Job lease/fencing、Schema INVALID、超时未知结果、日志与错误脱敏。真实 Provider 调用和客户数据外发不由本CR默认授权；使用合成内容完成协议验证后，再按用户明确的数据范围授权执行真实质量复验。

风险仍包括不同Provider的Token算法、模板转义、内容流读取期间撤权、调用超时后的远端未知结果和Suggestion正文保留。控制为Provider Adapter专属估算/硬上限、严格模板语法、读取前后双重Owner校验、逐次Invocation和未知结果状态，不以“发送成功”推断业务成功。
