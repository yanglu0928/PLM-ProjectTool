# AI-04-A06-P06-P02 Provider 执行合同

日期：2026-10-03；状态：`INTERNAL_PASS`；依据 CR-AI-015/017、DEC-745/746。

新增 provider-neutral 内部合同：

- `AIProviderExecutionRoute` 固定 Provider/Config/Model、OPENAI_COMPATIBLE、受信 endpoint policy/HTTPS URL、Secret root/version、model revision、region/egress class和响应/超时上限；URL与Secret标识不进repr。
- `AIProviderSendProof` 固定 Task/Invocation/Job/attempt/fencing、Content Plan、Authorization、Grant/Route/Payload摘要、字节/Token和有效期。`require_provider_send` 在 Adapter 之前强制 Route 摘要、Envelope逐字节摘要/长度/Token与时限一致。
- `AIProviderResponse` 在 P07 消费前持有受控 `bytearray`，repr不显示正文，关闭时就地清零；`AIProviderResponseObservation` 只暴露摘要、字节、usage、延迟和受限 finish reason。
- `AIProviderAdapterPort` 是唯一发送端口，接收Route/Proof/Envelope和短生命Secret memoryview；本项不实现Adapter。

安全URL合同只允许无凭据、无显式端口、无query/fragment、非IP/非Localhost、无路径穿越的HTTPS目标；DNS解析后全局IP检查留P06-P04运输层实施。当前仅固定 OPENAI_COMPATIBLE，其他 Provider kind不猜测映射。

Tests：单元5项覆盖正确Route/Envelope、Route/SecretVersion/Payload/过期漂移、URL安全、响应摘要与内存清零；后端全量 **2221项通过、3项既有条件跳过、无失败**；开发 wheel SHA-256 `38731f0ce54d2791e71f5f2b88f9aed04fd582e1270c89bbe5a3958fc1b6412b`。全程未读Secret、未联网、未创建/更改Invocation。

Changed/Files：Provider execution contract与单元测试。Migration/API/Dependencies：无。Compatibility/Rollback：未装配内部模块，可撤代码；不改Probe或历史。Known Issues：Route尚未从真实PG/Bootstrap导出，post-Begin pre-send Owner、SecretResolver/Adapter、受控网络和P07响应Owner待完成。Next：`AI-04-A06-P06-P03` 实现post-Begin pre-send当前事实与PostgreSQL Route/SecretVersion投影。
