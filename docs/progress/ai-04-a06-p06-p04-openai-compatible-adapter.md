# AI-04-A06-P06-P04 OpenAI-compatible 有界 ProviderAdapter

日期：2026-10-03；状态：`INTERNAL_PASS`；依据 CR-AI-017、DEC-745～748、P06-P02/P03。

新增独立业务 `PinnedHttpsOpenAICompatibleAdapter`，不复用或放宽固定Provider Probe。Adapter在网络前再次执行`require_provider_send`，严格解析provider-neutral Envelope，只把精确system/user messages、Route中的model key、`json_object`响应要求和`stream=false`转换为确定性OpenAI-compatible请求；Provider/Model或Envelope形态漂移在发送前拒绝。

生产网络边界固定443、隔离子进程DNS、全部候选地址必须为global IP、连接到已验证数字地址并以原hostname做SNI/证书校验；TLS最低1.2、系统CA、无代理、origin-form路径、无重定向。DNS/连接/读取/总时限及响应字节由受信Route限制。响应只接受HTTP 200、唯一Content-Length、identity编码和application/json；拒绝chunked、重复/折叠头、重定向、超限、截断和无效OpenAI响应。请求工作缓冲在发送后清零；响应交给P06-P02可清零对象。

Tests：新增5项单元，相关定向14项通过；Windows 11本地合成TLS服务完成证书hostname校验、origin-form请求、精确消息/model、无代理/重定向、usage/finish观察和受控响应清零。后端全量 **2230项通过、3项既有条件跳过、无失败**；开发wheel SHA-256 `0cf512ea16bb7082fcbf1d9e675b0d7c116501b20b7b34c90b6591d93bfb6b61`。未访问真实Provider、未使用客户数据或真实Secret。

Changed/Files：OpenAI-compatible Adapter、单元测试、本地合成TLS验证。Migration/API/Dependencies：无新增；使用既有Python标准库及已锁定`cryptography`测试依赖。Compatibility/Rollback：未装配内部增量，撤Adapter即可；固定Probe、Schema、API和历史不变。Known Issues：业务AIService发送步骤尚未把pre-send、精确SecretResolver与Adapter编排到同一调用；响应Schema/Invocation终态与Windows Worker尚待，Server 2025/Gate 3/UAT/可用包未完成。Next：`AI-04-A06-P06-P05-P01` 发送编排与SecretResolver接线前置核查。
