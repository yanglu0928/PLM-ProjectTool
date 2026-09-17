# POC-03 Embedding Provider 评估

## 状态

`PROPOSED_NOT_LIVE_VERIFIED`

## 2026-09-17 官方资料检查

- DeepSeek 官方 API 参考当前公开 Chat Completions、Responses 和模型列表；本轮没有找到官方 Embedding 端点。因此，不把现有 DeepSeek Key 或 Chat 模型假定为可生成向量。
- 阿里云百炼官方文档列出 `qwen3.7-text-embedding`，支持简体中文等 201 种语言/方言、OpenAI-compatible Embedding 调用，以及 1024 默认维度。
- 1024 维是官方文档建议的一般场景平衡值；但“文档支持”不等于“本项目已经实测”。

## 候选绑定

```text
provider: aliyun-model-studio-openai-compatible
model: qwen3.7-text-embedding
dimension: 1024
index_version: v1
```

该绑定当前仅为 PoC 候选，不能写成已冻结或已验证事实。只有使用对应区域的百炼 API Key 完成无客户数据的连通性/维度探测后，才允许激活索引并导出带该元数据的正式 Golden Dataset。

## 约束

1. 同一个 `index_id` 的 provider、model、dimension、index_version 不可原地改变。
2. 更换模型或维度必须创建新 `index_id`，随后全量重新 Embedding；旧向量不得复用。
3. API Key 只从本地 Secret/环境变量读取，不进入 Git、日志或报告。
4. 业务链路只通过统一 Embedding/AI 能力边界，不在业务模块直接调用厂商 SDK。

## 官方来源

- DeepSeek API 文档：https://api-docs.deepseek.com/
- DeepSeek API 参考：https://api-docs.deepseek.com/api/deepseek-api/
- 阿里云百炼 Embedding 文档：https://help.aliyun.com/en/model-studio/embedding

## 当前阻塞

缺少百炼对应区域的 API Key 和 Workspace/Base URL，故 live probe、索引激活和正式 Golden Dataset 导出暂不执行。

仓库已提供 `scripts/probe_embedding_provider.py`。脚本仅发送固定的非客户探测文本，Key 只从进程环境读取，成功报告仅保存 provider、model、请求/返回维度和输入数量。
