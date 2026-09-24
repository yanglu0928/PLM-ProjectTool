# ADR-004：统一 AI Gateway 与 RAG 平台

## Status

`ACCEPTED_FROM_BASELINE / NOT_GATE_2_FROZEN`

## Date

2026-09-22

## Context

交接、调研、需求、原型、方案、计划和输出均需要 AI 与检索能力。如果业务模块直接依赖厂商 SDK、模型名称或 pgvector SQL，会形成重复实现、凭据扩散、项目数据越权和不可审计的 Prompt 漂移。POC-03 还证明“链路可运行”不等于分类和引用质量达标。

## Decision

1. 所有模型调用固定经过 `AIService → ModelRouter → ProviderAdapter`；业务模块只提交 TaskType、RequiredCapabilities、PromptVersion、OutputSchema、RAGPolicy、Timeout 与 RetryPolicy。
2. 所有检索固定经过 `RetrievalService`；唯一主链为 Document → Parser → Chunk → Metadata → Embedding → pgvector/Full Text → Hybrid Retrieval → Reranker → Context Builder → AIService。
3. 知识域只分 `GLOBAL` 与 `PROJECT`。PROJECT 请求必须携带并再次授权 `project_id`，缺失或越权时失败关闭。
4. 一个有效索引只绑定一个 Embedding Provider、Model、Dimension 和 IndexVersion。更换模型或维度必须创建新索引并全量重建，不复用旧向量。
5. Prompt 由 PromptRegistry 版本化；AIInvocation 保存 Provider、Model、PromptVersion、InputVersion/Hash、结构化结果、Token、Latency 与脱敏错误。
6. AI 输出始终是 `SUGGESTION / NOT_FORMAL_FACT`；正式对象必须经业务规则、Evidence 与 ReviewService 人工确认。
7. 首批验收使用 DeepSeek，同时保留 OpenAI-compatible、Anthropic Messages、Gemini Native 和 Custom Adapter；Reranker 为可配置外部 API，服务器不做本地模型推理。
8. 客户资料发送至任何外部 Provider 前，仍需符合当轮明确的数据外发授权和最小必要载荷原则。

## Consequences

- 厂商替换、Prompt 版本、索引版本和调用审计集中管理。
- 业务模块不能绕过统一服务直接调用 Provider SDK、URL 或 pgvector SQL。
- 模型切换需要重建成本和双索引切换窗口，但避免向量语义不兼容。
- 外部 Provider 不可用时，系统必须返回可重试/不可重试状态；不能把空结果或低可靠度结果自动正式化。
- AI/RAG 质量仍需独立数据集验证，协议正确不代表业务准确。

## Rejected Alternatives

- 各业务模块自行调用模型：凭据、Prompt 和审计失控。
- 独立向量数据库：增加 V1 部署复杂度，当前 pgvector PoC 已满足链路需求。
- 本地大模型：超出最低资源和第一版 Scope。
- 原地替换 Embedding 模型：旧向量不可比较，可能产生静默质量回退。

## Rollback / Change Rule

可替换或新增 ProviderAdapter、PromptVersion 与 IndexVersion，而不改变业务 Contract。取消统一 AI/RAG 入口、引入独立向量库或本地模型属于架构/技术栈变更，必须走 L3 与新 PoC。

## References

- `docs/architecture/application-contracts-v1-candidate.md`
- `docs/progress/phase-0-summary.md`
- POC-03、POC-04 证据与《实施方案 V2.1》4.5～4.10
