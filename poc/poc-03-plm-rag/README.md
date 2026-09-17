# POC-03 PLM RAG

## Status

`IN_PROGRESS`

## Objective

验证统一 RAG 链路：`ParsedDocument → Chunk → Metadata → PostgreSQL 18/pgvector + Full Text → Hybrid Retrieval → Reranker → Context Builder → AIService`，并以 100~200 条经人工确认的 Golden Dataset 量化 Top-5 Recall、分类准确率和来源引用准确率。

本目录全部实现属于 Phase 0 验证性脚手架，不是已冻结的数据模型、API Contract 或正式业务实现。

## Environment

- 当前执行环境：Windows 11 x86-64，Python 3.13.x。
- PostgreSQL 18 + pgvector：复用 POC-02 已验证制品和证据。
- Document Parser：复用 POC-05 的 PoC `ParsedDocument` 输出。
- AI：只能通过 POC-04 的统一 `AIService` 边界调用 DeepSeek。
- Windows Server 2025、Debian 13：本 PoC 尚未执行。

## Input

- 本地 `方案库/`：18 个文件，共 365,328,831 字节；17 个受支持文件生成 13,710 个内容块。
- 本地 `技术协议&合同/`：18 个文件，共 38,808,615 字节；4 个 DOCX 和 5 个扫描 PDF 生成 46,720 个内容块。
- 两个目录均由 Git 忽略；合并输入为 26 个 ParsedDocument、60,430 个内容块。
- 两个资料库共 10 个旧版 `.doc` 不支持；当前仍缺少独立的标准能力和调研样本确认。

## Steps

1. 从 POC-05 本地 `ParsedDocument` 生成带 `scope`、`project_id`、来源定位和内容 Hash 的确定性 Chunk。
2. 按文档轮询抽样 120 条候选评审记录，避免由大文档垄断样本。
3. 所有候选记录标记为 `PENDING_HUMAN_REVIEW`；规则或 AI 输出不得直接成为 Golden Dataset 真值。
4. 人工补齐查询、相关性、分类、答案关键术语与引用标签，并按 Schema 验证为 100~200 条正式数据。
5. 在 PostgreSQL 18 + pgvector 上验证 ProjectId 隔离、FTS、Vector、Hybrid、Reranker 和 Context Builder。
6. 通过统一 AIService 执行端到端回归，计算并留存质量指标。

## Result

P0.09 候选准备链已通过：26 个 ParsedDocument 生成 655 个带 PROJECT/ProjectId 和来源定位的 Chunk，并轮询抽样 120 条候选记录，覆盖 26/26 个文档。所有候选仍为 `PENDING_HUMAN_REVIEW`；正式检索、Reranker、DeepSeek 端到端质量指标尚未运行。

## Metrics

|指标|目标|当前状态|
|---|---|---|
|候选评审记录|100~200 条|120 条，26/26 文档覆盖，PASS|
|正式 Golden Dataset|100~200 条|0 条 APPROVED；待人工确认|
|确定性 Chunk|可追溯且强制 PROJECT/ProjectId|655 个，PASS|
|Top-5 Recall|≥95%|NOT_RUN|
|分类准确率|≥90%|NOT_RUN|
|来源引用准确率|≥98%|NOT_RUN|
|PROJECT 跨项目泄漏|0|NOT_RUN|

## Logs

- 可提交脱敏证据：`evidence/windows-11/`。
- 候选正文、原始映射和运行输出：`artifacts/poc-03/`，由 Git 忽略。
- 原始方案文件与文件名映射不进入 Git。

## Known Issues

1. 当前方案库只有历史方案类资料，尚不能证明合同、技术协议、调研和标准能力四类覆盖完整。
2. 自动抽取只能形成候选集；没有人工批准的记录不得计入 Golden Dataset，也不得作为业务事实。
3. 两个资料库共 10 个旧版二进制 `.doc` 尚不支持，不进入本轮候选池。
4. Windows Server 2025 与 Debian 13 尚未执行本 PoC。

## Conclusion

POC-03 已启动，当前仅形成候选数据准备能力，不形成 RAG 质量通过结论。

## PASS / FAIL

`IN_PROGRESS`

## Alternative

- 如果现有方案库无法覆盖四类资料，保留覆盖缺口，补充脱敏标准能力、合同、技术协议和调研样本后再冻结 Golden Dataset。
- 如果外部 Reranker 不可用，记录失败证据并评估候选外部 API；不得擅自引入本地模型或独立向量库。
