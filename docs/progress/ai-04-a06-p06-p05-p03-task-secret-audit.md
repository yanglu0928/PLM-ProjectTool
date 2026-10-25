# AI-04-A06-P06-P05-P03 AI Task 专用 Secret 访问审计

日期：2026-10-03；状态：`INTERNAL_PASS`；依据 CR-AI-017、DEC-749～751、P05-P02。

新增 `AITaskProviderSecretAccessAudit`，在 SecretResolver 使用前以最小 ContextVar 身份绑定准确的 Project、原请求用户、Task、Invocation、Job generation、Route、SecretRecord 和 SecretVersion；不保存 Envelope、正文、密钥或 Provider 响应。作用域只接受与 Prepared Invocation、SendProof 和 Route 指纹完全一致的事实，拒绝未绑定、嵌套、错误 consumer、trace、Secret、Version 或 proof 漂移。

SecretResolver 的 `GRANTED`/`DENIED` 均通过真实 AuditService 在独立短事务写入 Project-scope `AI_PROVIDER_SECRET_ACCESS`：Actor 为当前受控 SYSTEM，OriginalActor 为 Task 原请求用户，目标固定 `platform/PLT-02` 及精确 SecretVersion，状态固定 `AI_TASK_SEND`。审计写入、受控 SYSTEM 身份复核或事务失败均失败关闭；业务审计不复用固定 Provider Probe 的身份或记录语义。

验证：新增单元 3 项及 8 个子用例；Windows 11/PostgreSQL 18.6 真实 Claim→Envelope→Begin→pre-send 后，以内存合成密文/解密器执行 SecretResolver，成功访问和错误期望版本分别持久化 `SUCCESS`/`DENIED`，错误版本在解密前拒绝，唯一明文 bytearray 离开作用域后全零；零真实 Secret、零 Provider 网络。后端全量 **2231 项通过、3 项既有条件跳过、2907 个子用例、无失败**；开发 wheel SHA-256 `5918f56a12390f5a2ed225fd2b0d02b37bc0bd6a557d3c76264e2f68b2e80f9e`。首次误用仅含运行依赖的旧 PoC venv 执行 pytest 导致测试工具缺失，改为仓库现有 Python 3.13 测试模块加该 venv 运行依赖后完整重跑，产品代码与依赖未改变。

Changed/Files：新增 Task Secret 审计适配器、单元和 PostgreSQL 组合验证；为 P06-P03 验证器增加默认关闭的 after-authorized 回调。Migration/API/Dependencies：无。Compatibility/Rollback：未装配内部增量，可停止业务 AI 消费并撤适配器；Schema、冻结 API、Probe 和历史数据不变。Known Issues：尚未把首次 pre-send、SecretResolver、第二次 pre-send 和 Adapter 严格编排成一个发送入口；响应 Schema/Invocation 终态、Windows Worker、Server 2025、Gate 3/UAT/可用程序包仍待。Next：`AI-04-A06-P06-P05-P04` 双 pre-send + 精确 SecretVersion + Adapter 顺序编排。
