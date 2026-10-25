# POC-04 AI Gateway / DeepSeek 验收矩阵

|ID|验收项|Windows 11|Windows Server 2025|Debian 13|证据要求|
|---|---|---|---|---|---|
|P04-A01|环境与依赖采集|PASS|PASS|DEFERRED_BY_USER|Python、httpx、jsonschema、OS|
|P04-A02|统一 AIService / ModelRouter / ProviderAdapter|PASS|PASS|DEFERRED_BY_USER|架构边界测试|
|P04-A03|文本响应|PASS_MOCK|PASS_MOCK|DEFERRED_BY_USER|确定性协议测试|
|P04-A04|SSE 流式响应|PASS_MOCK|PASS_MOCK|DEFERRED_BY_USER|Chunk 拼接与 `[DONE]`|
|P04-A05|结构化 JSON 与本地 Schema|PASS_MOCK|PASS_MOCK|DEFERRED_BY_USER|JSON Output 请求与 Schema PASS|
|P04-A06|超时映射与受控重试|PASS_MOCK|PASS_MOCK|DEFERRED_BY_USER|3 次后 `AI_TIMEOUT`|
|P04-A07|503 重试恢复|PASS_MOCK|PASS_MOCK|DEFERRED_BY_USER|首次失败、第二次成功|
|P04-A08|无效密钥 401|PASS_MOCK|PASS_MOCK|DEFERRED_BY_USER|不重试，`AI_AUTH_FAILED`|
|P04-A09|HTTP 429|PASS_MOCK|PASS_MOCK|DEFERRED_BY_USER|重试恢复，`AI_RATE_LIMIT`|
|P04-A10|Schema failure|PASS_MOCK|PASS_MOCK|DEFERRED_BY_USER|`AI_SCHEMA_INVALID`|
|P04-A11|真实 DeepSeek 401 连通性|PASS|PASS|DEFERRED_BY_USER|HTTP 401 映射 `AI_AUTH_FAILED`，未使用真实密钥|
|P04-A12|真实 DeepSeek 文本/流式/结构化|PASS|PASS|DEFERRED_BY_USER|本地 Secret、脱敏结果、模型与耗时|
|P04-A13|流式中断防重复|PASS_MOCK|PASS_MOCK|DEFERRED_BY_USER|首个 Chunk 后中断只执行一次|
|P04-A14|JSON/Schema 受控重试|PASS_MOCK|PASS_MOCK|DEFERRED_BY_USER|空 JSON 第二次恢复；连续失败第三次返回标准错误|

## 状态定义

- `PASS`：本机已执行且满足证据要求。
- `PASS_MOCK`：使用确定性 HTTP Mock 验证协议与控制逻辑；不得描述为 DeepSeek 线上通过。
- `BLOCKED_SECRET`：缺少本地配置的真实密钥；不得把密钥写入仓库、日志或聊天。
- `NOT_RUN`：未执行。
- `DEFERRED_BY_USER`：用户已明确批准暂缓，并已登记独立例外；不得描述为通过。
- `FAIL`：已执行但不满足要求，需保留失败分析。

Windows 11 与 Windows Server 2025 的真实 DeepSeek 文本、SSE 流式和结构化 JSON 已全部通过。Debian 13 依据 `EXC-P0-003` 暂缓且保持未验证，POC-04 以 `PASS_WITH_EXCEPTION` 收口。
