# POC-04 AI Gateway / DeepSeek

## Status

`IN_PROGRESS`

## Objective

验证统一 `AIService → ModelRouter → ProviderAdapter` 技术路径，并以 DeepSeek Chat Completions 协议覆盖文本、SSE 流式、结构化 JSON、超时、重试、无效密钥、HTTP 429 和 Schema failure。业务调用只依赖统一合同，不直接依赖 DeepSeek URL 或厂商 SDK。

本目录全部代码属于 Phase 0 验证性脚手架，不是已冻结的正式 API Contract。

## Environment

- Windows 11 Home 10.0.26200，x86-64。
- Windows Server 2025 Datacenter 10.0.26100，x86-64。
- Python 3.13.15。
- httpx 0.28.1。
- jsonschema 4.26.0。
- Debian 13：`NOT_RUN`。
- `DEEPSEEK_API_KEY`：仅从本地 Secret 或来宾机临时文件读取；任何证据都不得记录 Secret 值。

## Input

- 官方协议快照：`official-docs-snapshot.md`。
- 确定性 MockTransport 响应：文本、SSE、JSON、401、429、503、timeout、Schema failure。
- 真实 DeepSeek：只允许从本机环境变量读取密钥，禁止命令行参数、仓库文件和日志保存密钥。

## Steps

1. 注册 `DeepSeekAdapter` 到 `ModelRouter`，业务请求只进入 `AIService`。
2. 执行文本和 SSE 协议验证。
3. 执行 JSON Output 请求，并在网关侧按 Draft 2020-12 JSON Schema 验证。
4. 验证 401 不重试，429/500/503 与 timeout 仅按受控策略重试。
5. 验证流式响应在已经输出 Chunk 后失败时不自动重试，避免重复内容。
6. 执行真实 DeepSeek 401 连通性探针。
7. 在本机安全配置真实密钥后执行文本、流式和结构化线上验证。

## Result

|验收域|Windows 11|Windows Server 2025|Debian 13|说明|
|---|---|---|---|---|
|统一 AIService / ModelRouter / ProviderAdapter|PASS|PASS|NOT_RUN|业务入口不包含厂商 URL 或 SDK|
|确定性协议与异常场景|PASS|PASS|NOT_RUN|两端均为 11/11 场景通过|
|单元测试|PASS|PASS|NOT_RUN|两端均为 11/11 测试通过|
|真实 DeepSeek 无效密钥|PASS|PASS|NOT_RUN|HTTP 401 映射 `AI_AUTH_FAILED`，不重试|
|真实 DeepSeek 文本|PASS|PASS|NOT_RUN|预期输出精确匹配|
|真实 DeepSeek SSE 流式|PASS|PASS|NOT_RUN|Chunk 拼接与预期输出匹配|
|真实 DeepSeek 结构化 JSON|PASS|PASS|NOT_RUN|JSON 解析与本地 Schema 通过|

真实结构化调用第一次返回不可解析 JSON，网关当时没有对 JSON/Schema failure 重试，结果为 FAIL。修复后，`AI_JSON_INVALID` 与 `AI_SCHEMA_INVALID` 纳入最多 3 次受控重试；第二次真实全量复跑三场景全部 PASS。首次失败证据保留在 `live-validation-result-attempt-1.json`。

## Metrics

|指标|Windows 11|Windows Server 2025|
|---|---|---|
|单元测试|11/11 PASS|11/11 PASS|
|确定性协议与异常场景|11/11 PASS|11/11 PASS|
|真实 401 连通性|PASS，0.463 秒|PASS，0.474 秒|
|真实文本|PASS，0.834 秒|PASS，1.055 秒|
|真实 SSE 流式|PASS，0.857 秒|PASS，0.804 秒|
|真实结构化 JSON|PASS，0.931 秒|PASS，0.918 秒|
|Secret 或响应正文写入证据|0|0|

MockTransport 的亚毫秒耗时只用于代码路径回归，不代表生产网络性能。

## Logs

- 可提交脱敏证据：`evidence/windows-11/`、`evidence/windows-server-2025/`。
- 原始临时输出：`artifacts/poc-04/`，由 Git 忽略。

## Known Issues

1. MockTransport 只能验证网关逻辑和协议解析；真实文本、流式与结构化已另行验证，但尚未形成质量、并发或容量结论。
2. 当前默认模型名来自 2026-09-17 官方文档快照，正式开发时必须配置化，不得在业务模块硬编码。
3. Debian 13 尚未执行。
4. DeepSeek 官方说明 JSON Output 偶尔可能返回空内容；本 PoC 使用最多 3 次受控重试，连续失败后返回 `AI_JSON_INVALID` 或 `AI_SCHEMA_INVALID`，不把无效结果写成业务事实。

## Conclusion

Windows 11 与 Windows Server 2025 上统一 AI Gateway 与 DeepSeek Chat Completions 技术路径可行：真实文本、SSE 流式、结构化 JSON 和无效密钥均已通过，异常、重试及业务层厂商隔离由确定性场景覆盖。

POC-04 仍为 `IN_PROGRESS`。Debian 13 尚未执行或取得本 PoC 独立例外，不形成 Debian 平台结论。

## PASS / FAIL

`IN_PROGRESS`

## Alternative

- 若 DeepSeek OpenAI 格式在目标网络不可用，先保留失败证据，再评估 DeepSeek 其他官方协议入口或代理网络；不得直接替换首批实际验收 Provider。
- 若 JSON Output 返回空内容或不满足业务 Schema，网关必须返回标准 Schema 错误并允许人工重试；不得把无效输出写成正式业务事实。
