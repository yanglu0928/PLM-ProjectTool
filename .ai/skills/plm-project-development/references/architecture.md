# 架构与领域约束

## 总体形态

第一版固定采用模块化单体：单一部署、内部模块化、稳定 Contract。模块至少包括：

```text
platform auth project workflow document evidence review trace audit
ai rag jobs
capability handover survey requirement prototype solution plan
plugin license developer_workbench
```

依赖方向必须保持：

```text
UI → API → Application Service → Domain → Repository / Gateway
```

模块间只通过 Application Interface、Domain Event、TraceLink 和 DTO/Contract 通信。禁止 UI 直连数据库、插件直连数据库、业务模块访问其他模块内部表，或下游模块直接写上游模块表。

## 统一能力入口

- AI：`AIService → ModelRouter → ProviderAdapter`。
- 检索：统一 `RetrievalService`，业务模块不得直接写 pgvector SQL。
- 插件：统一 `PluginService`，业务模块不得直接操作子进程。
- 追溯：统一 `TraceService`。
- 评审：统一 `ReviewService`。

业务模块只声明 TaskType、RequiredCapabilities、PromptVersion、OutputSchema，不写厂商判断分支。

## AI 与 Prompt

统一 Task Type：

```text
DOCUMENT_PARSE
CAPABILITY_EXTRACT
GAP_ANALYSIS
SURVEY_GENERATE
SURVEY_ANALYZE
REQUIREMENT_NORMALIZE
REQUIREMENT_MATCH
SOLUTION_SUGGEST
PROTOTYPE_GENERATE
SOLUTION_GENERATE
PLAN_GENERATE
OUTPUT_SUMMARIZE
```

每类任务必须绑定 PromptVersion、ProviderPolicy、OutputSchema、RAGPolicy、Timeout、RetryPolicy。

Prompt 必须由 PromptRegistry 管理，包含 PromptId、TaskType、Version、SystemPrompt、UserTemplate、OutputSchema、Status、CreatedAt。任何修改产生新版本；AI 调用保存模型、Provider、PromptVersion、InputVersion 和 Output。

## RAG

唯一公共链路：Document → Parser → Chunk → Metadata → Embedding → pgvector/Full Text → Hybrid Retrieval → Reranker → Context Builder → LLM。

- 知识域仅分 GLOBAL 与 PROJECT；PROJECT 检索必须强制 ProjectId 过滤。
- 一个有效索引只能绑定一个 Embedding Model，并保存 provider、model、dimension、index_version。
- 更换模型时新建索引并全量重新 Embedding，禁止复用旧向量。
- 标准能力匹配必须结合 Vector、Full Text、Metadata、Rerank、LLM 和人工确认。
- 允许输出：标准满足、部分满足、非标准、资料不足、无可靠匹配、需人工确认。

## 业务事实、版本和 Trace

- AI Requirement Suggestion 不等于 Formal Requirement。
- AI Solution Suggestion 不等于 Formal Solution。
- AI Generated Section 不等于 Formal Solution Section。
- Evidence、Questionnaire、Requirement、Prototype、Solution、正式附件不得覆盖历史版本。
- 合同 → 调研 → 需求 → 解决方案 → 原型 → 方案 → WBS 必须通过 TraceLink 连通。

## Review Engine

调研结论、正式需求、原型、正式方案复用统一 Review Engine：项目负责人发起，指定 1~N 位客户确认人；所有人处理完才判定；任一退回则本轮退回；退回意见必填；送审期间锁定；修改后升版重审；历史确认永久保留。

