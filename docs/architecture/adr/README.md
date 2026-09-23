# Architecture Decision Records

本目录保存影响多个 WBS 或长期兼容性的架构决策。`ACCEPTED_FROM_BASELINE / NOT_GATE_2_FROZEN` 表示该决策继承已批准的 V2.1、Phase 0 或用户例外，但完整 Architecture/Data/API 基线仍需 Gate 2 正式确认。

|ADR|主题|状态|主要 Gate|
|---|---|---|---|
|ADR-001|三平台正式目标|Accepted|Release|
|ADR-002|Ghostscript AGPL 源码公开策略|ACCEPTED_WITH_RELEASE_GATE|Release|
|ADR-003|模块化单体|ACCEPTED_FROM_BASELINE|Gate 2|
|ADR-004|统一 AI Gateway 与 RAG|ACCEPTED_FROM_BASELINE|Gate 2 / Gate 3|
|ADR-005|Plugin 独立进程与 stdio|ACCEPTED_FROM_BASELINE|Gate 2 / Release|
|ADR-006|License 与可信时间|ACCEPTED_FROM_BASELINE|Gate 2 / Release|
|ADR-007|PostgreSQL Job/Outbox|ACCEPTED_FROM_BASELINE|Gate 2|
|ADR-008|本地文件 + PostgreSQL 元数据|ACCEPTED_FROM_BASELINE|Gate 2 / Release|
|ADR-009|POC-03 质量替代控制|ACCEPTED_EXCEPTION|Gate 3 / UAT|

## 变更规则

- Gate 2 前：候选细节可调整，但不得越过锁定技术栈、用户批准例外或 L3 边界。
- Gate 2 后：影响总体架构、技术栈、安全/License、Breaking API 或核心数据模型的修改必须提交独立 Change Request。
- ADR 被替代时保留原文件，状态改为 Superseded，并链接替代 ADR；不得删除历史决策。
