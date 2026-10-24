# POC-04 Windows 11 证据

## Environment

- Windows 11 Home 10.0.26200，AMD64。
- Python 3.13.15。
- httpx 0.28.1。
- jsonschema 4.26.0。

## Result

- 单元测试：11/11 PASS。
- 确定性 MockTransport 场景：11/11 PASS。
- DeepSeek 官方端点无效密钥：HTTP 401，正确映射为 `AI_AUTH_FAILED`，PASS。
- 真实 DeepSeek 文本：PASS。
- 真实 DeepSeek SSE 流式：PASS。
- 真实 DeepSeek 结构化 JSON：PASS。
- 业务层厂商隔离：PASS。

## Failure and Fix

第一次真实调用中，文本与 SSE 流式通过，结构化 JSON 返回不可解析内容，结果为 `AI_JSON_INVALID`。该证据保留为 `live-validation-result-attempt-1.json`。

根因不是鉴权或网络失败，而是网关只重试 HTTP/timeout，没有覆盖模型返回的 JSON/Schema failure。修复后增加：

1. `AI_JSON_INVALID` 最多 3 次受控重试。
2. `AI_SCHEMA_INVALID` 最多 3 次受控重试。
3. 首次空 JSON、第二次恢复的确定性回归。
4. 连续 3 次 Schema failure 后返回标准错误的回归。

第二次真实全量复跑三场景全部 PASS。

## Privacy

- API Key 只从仓库外本地文件读取并注入子进程环境变量。
- Key 文件被 `.gitignore` 精确排除。
- 证据不保存 Key、Authorization Header、Prompt 或模型响应正文。
- 证据只保存模型名、Base URL、状态、标准错误码、布尔匹配结果和耗时。

## Files

- `environment.json`：运行环境。
- `validation-result.json`：确定性 MockTransport 最终结果。
- `validation-result-attempt-1.json`：证据脚本首次判定缺陷记录。
- `live-invalid-key-result.json`：真实 401 连通性结果。
- `live-validation-result-attempt-1.json`：真实结构化首次失败结果。
- `live-validation-result.json`：修复后的真实三场景结果。
