# CR-AI-017：业务 AI 调用不得复用固定 Provider 探针作为发送器

日期：2026-10-03；状态：依 V1.1 持续授权登记，实施中（P06-P02～P04已通过）；关联 Gate 2 冻结 ADR-004/DM-04/API-03、CR-AI-002/003/015/016、Schema0073；原冻结提交 `64cdf09` 不改。WBS `AI-04-A06-P06`。

## 冲突与证据

P05已在任何网络 I/O 前完成真实 Job Claim、服务端 Envelope/payload proof 和 PENDING Invocation。但现有 `AI_PROVIDER_WORKER` 只服务 Provider Test：专用 Claim/Result、固定 `ping`、固定 1 token、最多 16 KiB 响应，且运输层自行构造请求并丢弃业务响应。它不接受已批准 Envelope，不绑定 AI Task/Invocation/Egress Authorization，也不能产生后续 Schema 验证所需的受控结果。直接复用会绕过冻结 `AIService → ModelRouter → ProviderAdapter` 和逐次外发边界。

P05 的 Grant Repository 只允许 `QUEUED + no current Invocation`，Begin 后 Task 已为 `RUNNING + PENDING Invocation`，因此不能在发送前盲目重用原 Grant Issuer。必须新建 post-Begin pre-send Owner，以 PENDING Invocation 为根复核当前 Lease/Fencing、Task/Plan/payload proof、未撤销 Authorization、License、Provider/Config/Model 路由和当前 ACTIVE SecretVersion。

现有 `SecretResolver` 已提供 `AI_PROVIDER_ADAPTER` 限定、期望 SecretVersion、解密后内存清零与访问审计，可在新 Adapter 调用瞬间复用。现有受信 `ai_probe_policies` 则把 endpoint 与单一探针 model 绑定，不是业务 ModelRouter 策略；Provider API 中的 `endpoint_policy_ref` 只是符号引用，不得由数据库或 HTTP 传入任意 URL。

## 方案与决定

- A：直接将 Provider Probe Transport 改成可发任意正文。否决；会破坏探针“固定无客户数据”边界并混淆两种 Claim/结果语义。
- B：从 ProviderConfig 或 Job payload 直接取 URL/model/key。否决；会引入 SSRF、Secret 外泄和未审部署路由。
- C：新建业务执行专用的非秘密受信 endpoint policy/ModelRouter、post-Begin pre-send proof 与 ProviderAdapter；只复用 SecretResolver 及经抽取后的安全 TLS/DNS/有界响应原语，不复用固定探针业务接口。选择 C。

## 切片、兼容与回滚

1. P06-P02：定义无正文 execution route/send proof/Adapter observation 合同，要求 Provider/Config/Model/region/endpoint policy/SecretVersion/Invocation/Grant/payload 精确一致。
2. P06-P03：实现 post-Begin PostgreSQL pre-send Owner，短事务锁定 PENDING Invocation、RUNNING Task、当前 Claim/Authorization/Provider route/SecretVersion，提交后再验 License。
3. P06-P04：实现 OpenAI-compatible 有界 ProviderAdapter 和独立的非秘密 execution policy registry；请求必须发送 Envelope 规范字节的等价语义，禁止重定向/代理/私有地址，并限制 DNS、连接、读取、总时间与响应字节。
4. P06-P05起：组合 AIService 发送步骤和 Windows Worker；合成 Adapter 先验证，真实 Provider/客户数据仍需该轮明确授权。响应只交给 P07 的 Schema/Suggestion Owner，不进普通日志。

无已发行业务 Adapter，所以追加受信部署策略和内部 Port 不破坏公开 `/api/v1`。原 Probe Worker 和 `ai_probe_policies` 保持不变。回滚为不装配业务 Worker/执行策略，恢复不消费；已存 PENDING Invocation 保留并由后续对账收敛，不删除。

## 验证与剩余风险

单元覆盖策略严格形状、未知 Provider/model/endpoint、URL/DNS/redirect/proxy/字节/时间上限、Envelope一字节漂移、SecretVersion变化、网络前 Lease/授权/License 撤销、内存/日志脱敏。PostgreSQL覆盖并发 fencing、Task/Invocation状态、路由/密钥轮换、事务回滚。网络合成先用本地受控 TLS 替身；任何真实 Provider 调用均必须有当轮明确数据范围授权。剩余风险包括 Provider 差异、超时后远端结果未知、结构化输出和 usage/token 语义，分别由 Adapter 版本、UNKNOWN 终态和 P07/P08 关闭。

P06-P02已实现无正文Route/SendProof/Response/Adapter Port合同：Route固定endpoint policy/URL、Provider/Config/Model、SecretVersion、region/egress class和有界超时/响应；SendProof将Invocation/Job generation/Grant/Authorization/Plan/Route/Envelope绑定；响应正文由可清零bytearray管理且不进repr。单元5、后端2221运行/3跳过及wheel通过；无Secret读取、网络、Schema/API/依赖变化。P06-P03继续post-Begin PostgreSQL pre-send Owner。

P06-P03已实现post-Begin pre-send Owner、受信execution policy registry和PostgreSQL current route投影：同一短事务锁定当前Job generation、RUNNING Task/PENDING Invocation、未撤销授权、ACTIVE Provider/current Config、AVAILABLE CHAT Model和ACTIVE SecretVersion，事务内外双验License，再生成Route/SendProof。Win11/PG18.6真实链证明Inactive Secret和暂停Model失败关闭；单元4、相关定向12、后端2225运行/3跳过及wheel通过。无Secret解密、网络、Schema/API/依赖变化。P06-P04继续实现有界OpenAI-compatible Adapter与合成TLS网络边界。

P06-P04已实现独立OpenAI-compatible业务Adapter：网络前复核SendProof，确定性转换精确messages/model；隔离DNS且全部候选须global、数字IP pinning、原hostname SNI/证书、TLS≥1.2、系统CA、无代理/重定向，并限制各阶段时长、Content-Length和响应字节。Windows 11本地合成TLS、单元5、相关定向14、后端2230运行/3跳过及wheel通过；未接真实Provider/客户数据/真实Secret。P06-P05起组合pre-send、SecretResolver和Adapter，再进入响应Schema/终态。

P06-P05-P01前置核查发现当前AI Task Claim/SendProof未携带Lease截止时间，而Route总网络时限最长120秒；仅在pre-send瞬间验证Lease无法证明调用可在当前generation租约内结束。另发现Probe专用Secret审计不能承载业务Task身份。P06-P05拆为：P02补数据库观察时间/Lease截止与`lease_expires_at-total_timeout-margin`开始截止；P03新增业务Task Secret审计；P04以pre-send→精确SecretVersion解析→再次pre-send/Route一致→Adapter顺序执行。此修订无Schema/API/依赖变化，不放宽外发授权。

P06-P05-P02已完成：AI Task Claim由数据库投影`observed_at/lease_expires_at`，pre-send要求剩余Lease严格覆盖Route总时限+2秒，并把SendProof开始截止收紧到`min(authorization, lease-total-margin)`。Win11/PG18.6 21秒窗口拒绝、120秒窗口成功，相关定向16、后端2231运行/3跳过及wheel通过；无Schema/API/依赖/Secret/网络。P03继续Task专用Secret审计。

P06-P05-P03已完成：新增业务 Task 专用 Secret 审计作用域，把 Project/原请求用户/Task/Invocation/Job generation/Route/SecretRecord/SecretVersion 精确绑定到最小 ContextVar；仅在绑定内接受 AI_PROVIDER_ADAPTER 的 GRANTED/DENIED，并通过真实 AuditService 写 Project-scope SYSTEM/original-user 事件。Win11/PG18.6真实链证明成功和错误版本拒绝均落审计、错误版本不解密、明文缓冲区清零；单元3、后端2231运行/3跳过及wheel通过，零真实Secret/Provider网络。P04继续双pre-send、精确SecretVersion解析和Adapter顺序编排。

P06-P05-P04已完成：唯一内部发送入口按首次pre-send→Task审计/trace→精确SecretVersion读取→第二次pre-send→Route/Proof稳定性→Adapter顺序执行，任何轮换、授权/Lease/License、身份/摘要或审计漂移均在Adapter前失败关闭；密钥和错误路径清零。Win11/PG18.6使用真实pre-send、PostgreSQL Secret Store和Project Audit及合成Adapter通过，相关定向17、后端2235运行/3跳过及wheel通过，零真实Secret/Provider网络。一次方法调用最多一次Adapter不等于跨崩溃远端exactly-once；P07/P08继续响应Schema、Suggestion/Invocation终态、UNKNOWN和对账。
