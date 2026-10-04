# DeepSeek 官方协议快照

- 核对日期：2026-09-17。
- OpenAI 格式 Base URL：`https://api.deepseek.com`。
- 本 PoC 选用接口：`POST /chat/completions`。
- 本 PoC 默认模型：`deepseek-flash`，可通过配置替换，不写入业务模块。
- 鉴权：HTTP Bearer。
- Chat Completions 流式格式：data-only SSE，以 `data: [DONE]` 结束。
- JSON Output：请求包含 `response_format: {"type": "json_object"}`，提示词同时明确要求 JSON；网关收到结果后仍执行本地 JSON Schema 校验。
- 错误处理：401 不重试；429、500、503 可按受控策略重试；400、422 作为请求错误，不自动重试。

官方来源：

- https://api-docs.deepseek.com/
- https://api-docs.deepseek.com/api/create-chat-completion/
- https://api-docs.deepseek.com/guides/json_mode/
- https://api-docs.deepseek.com/quick_start/error_codes/
- https://api-docs.deepseek.com/quick_start/rate_limit/

该快照只记录本轮 PoC 使用的协议事实，不冻结具体模型名称、价格或并发额度；正式开发前仍需通过 Provider 配置与 ADR 冻结策略。
