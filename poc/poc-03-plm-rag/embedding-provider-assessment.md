# POC-03 Embedding Provider 评估

## 状态

`PASS_POC_LIVE_VERIFIED`

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

该绑定已使用华北 2（北京）OpenAI-compatible 端点和固定非客户探测文本完成实测：请求维度 1024，返回维度 1024。它是 POC-03 的已激活验证绑定，不代表正式架构冻结。

## 约束

1. 同一个 `index_id` 的 provider、model、dimension、index_version 不可原地改变。
2. 更换模型或维度必须创建新 `index_id`，随后全量重新 Embedding；旧向量不得复用。
3. API Key 只从本地 Secret/环境变量读取，不进入 Git、日志或报告。
4. 业务链路只通过统一 Embedding/AI 能力边界，不在业务模块直接调用厂商 SDK。

## P03-A05 换模重建验证

- 官方 OpenAI-compatible 文档确认华北 2（北京）支持 `text-embedding-v4`，并支持 768 维输出。
- 旧绑定：`qwen3.7-text-embedding`、1024 维、index `v1`。
- 新验证绑定：`text-embedding-v4`、768 维、新 index `v2`。
- 旧 index_id 原地换模由绑定注册器拒绝。
- 使用 120 条固定非客户文本执行 12 批真实 Embedding 请求，120/120 返回 768 维，旧向量复用 0。
- 新 `v2` 仅为 P03-A05 验证制品，状态 `VALIDATED_NOT_ACTIVATED`；当前激活绑定仍为 `v1`。

## 官方来源

- DeepSeek API 文档：https://api-docs.deepseek.com/
- DeepSeek API 参考：https://api-docs.deepseek.com/api/deepseek-api/
- 阿里云百炼 Embedding 文档：https://help.aliyun.com/en/model-studio/embedding
- 阿里云百炼 Base URL 文档：https://help.aliyun.com/en/model-studio/base-url
- 阿里云百炼 OpenAI-compatible Embedding：https://help.aliyun.com/en/model-studio/embedding-interfaces-compatible-with-openai

## 当前阻塞

Embedding provider 与维度不再阻塞。109 条人工批准记录已完成 Schema 合法导出，但覆盖审计发现仅 1 个唯一查询、1 种来源类型和 1 种分类；该数据集不能进入 RAG 指标计算，需先修正人工标签覆盖。

仓库已提供 `scripts/probe_embedding_provider.py`。脚本仅发送固定的非客户探测文本，Key 只从进程环境读取，成功报告仅保存 provider、model、请求/返回维度和输入数量。
