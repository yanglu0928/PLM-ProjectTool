# AI-04-A04-P02：Egress Preview / SourceRef Schema0068

- 日期：2026-10-03
- 结果：PASS（Windows 11 / PostgreSQL 18.6 隔离验证）
- 依据：CR-AI-013、DEC-706～707、冻结 `EGRESS_PREVIEW_CREATE/GET`

Schema0068 新增 `ai_egress_previews` 权威预览根与 `ai_egress_preview_source_refs` 不可变来源引用。预览固定 Scope/Project、Purpose/Operation、Provider/Config/AVAILABLE Model/Region、数据类别、最小载荷策略、定量上限、Payload/Source 指纹、风险代码、创建人/追踪及有效期；不保存正文、Prompt、Key 或 Secret。

数据库拒绝零 UUID、跨项目来源、相同预览下重复语义来源、重复/空/越界集合值、Provider/Config/Region 或 Model 归属不一致；Preview 和 SourceRef 都只能插入，禁止改删/Truncate。空表可降级并重升，有历史时拒绝物理降级。

验证：Win11 隔离 PG18.6 空库 up/down/re-up、Alembic drift=0、Provider/Model/Region、集合与 UUID、来源 Scope/去重/不可变及非空拒降均 PASS；后端 2111 运行/3 跳过 PASS。开发 wheel SHA-256 `9f7f479e00258503511e43238d637662bc5ed772608798f183dc7d867c32c01e`。

边界：0068 仅建立预览及来源证据；Authorization/撤销历史、应用服务、HTTP/组合根与真实外发均未开放。
