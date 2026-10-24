# AI-04-A06-P06-P03 Provider 发送前当前事实 Owner

日期：2026-10-03；状态：`INTERNAL_PASS`；依据 CR-AI-015/017、DEC-745～747、Schema0073。

本项新增独立于 QUEUED-only Grant Issuer 的 post-Begin Owner。它在一个短事务内重新检查当前 Job lease/attempt/fencing、RUNNING Task、唯一 PENDING Invocation、Content Plan、payload fingerprint、未撤销 Egress Authorization、ACTIVE Provider/current Config、AVAILABLE CHAT Model 和 ACTIVE SecretVersion；再由受信 deployment execution policy 将数据库中的符号 endpoint reference 映射到严格 HTTPS URL、允许模型、region/egress class及响应/超时上限。事务内和事务关闭后各复核一次 License，最终生成与实际 Route、Invocation、Grant 和 Envelope绑定的 `AIProviderSendProof`。

安全边界：Repository只投影Secret root/version标识，不读取或解密密文；策略URL不是数据库或请求方输入；本项不调用Adapter、不访问DNS/网络、不记录正文。Provider Test的固定`ping`路径保持不变。

Tests：新增4项pre-send单元测试；相关定向12项通过。Windows 11/PostgreSQL 18.6隔离组合从真实HTTP Task、Job Claim、精确Envelope和PENDING Invocation继续执行，证明Inactive Secret、暂停Model均失败关闭，恢复当前状态后Route/SendProof匹配；零Secret解密和零Provider I/O。后端全量 **2225项通过、3项既有条件跳过、无失败**；开发wheel SHA-256 `efffd47597b53e6a83a06c660129db4b16793321a9d876fca2c1acae9dae7cbc`。

Changed/Files：execution policy registry、pre-send application service、PostgreSQL route repository、单元与隔离组合验证，并为P05-P04验证器增加默认关闭的after-Begin回调。Migration/API/Dependencies：无。Compatibility/Rollback：未装配内部增量，可撤新组件及验证回调；不改变Schema、冻结API、Probe或历史Invocation。Known Issues：尚未实现受控DNS/TLS/禁止代理与重定向的OpenAI-compatible Adapter，SecretResolver尚未接到业务调用瞬间；响应Schema/终态、Server 2025、Gate 3/UAT/可用程序包仍待。Next：`AI-04-A06-P06-P04` 实现有界OpenAI-compatible ProviderAdapter及合成TLS网络验证。
