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
4. 可先运行完全本地的规则生成器预填查询、分类、答案关键术语和引用定位，再由人工逐条或抽样修正；预填结果不得直接变成正式数据。
5. 使用 `scripts/import_review_workbook.py` 复核不可变来源字段，只导出人工 `APPROVED`、字段完整且引用仍在原候选定位范围内的记录。
6. 在 PostgreSQL 18 + pgvector 上验证 ProjectId 隔离、FTS、Vector、Hybrid、Reranker 和 Context Builder。
7. 通过统一 AIService 执行端到端回归，计算并留存质量指标。

## Result

P0.09 候选准备链已通过：26 个 ParsedDocument 生成 655 个带 PROJECT/ProjectId 和来源定位的 Chunk，并轮询抽样 120 条候选记录，覆盖 26/26 个文档。旧 R1 曾导出 109 条记录，但覆盖审计仅有 1 个唯一查询、1 种来源类型和 1 种分类，已判定不可用于质量指标。用户已填写 R2 的 120 行审核状态、审核人和日期；独立 Gate 复核显示 45 行字段完整，75 行仍缺锁定的来源类型，不能因填写 `APPROVED` 自动视为正式数据。R3 将其转换为人工确认待办交互原型：主表不再展示大段正文，提供 120 个本地证据定位链接和逐项维护提示，同时完整保留 R2 技术评审页。P03-A04 使用百炼 `qwen3.7-text-embedding` 实测请求/返回 1024 维，索引 `v1` 绑定 PASS。

## Confirmation UX Prototype

R3 是对用户体验的 Phase 0 验证，不是正式项目交接 `ActionItem` 模块。它验证“AI 发现 → 打开证据 → 人工确认/修改/退回”的交互方式：

- 主清单只显示问题、风险、AI 建议、需确认事项和人工决定。
- 每条记录可打开同目录本地证据页；PDF 携带页码，Office 文档显示精确段落、表格或幻灯片定位并可打开原文件。
- 人工输入列明确标色并说明需要维护的内容。
- 原 R2 数据只读保留在技术审计页，用户已填写内容不被覆盖。
- 详细边界和正式模块建议见 `confirmation-ux-prototype.md`。

## Local Review Prefill

预填过程不调用外部 AI 服务，候选正文和建议内容只写入 Git 忽略的本地输出：

```powershell
python scripts/generate_review_suggestions.py `
  --candidates <本地候选集.jsonl> `
  --local-output <本地建议.json> `
  --sanitized-report <脱敏报告.json>
```

生成器不会填写审核人或审核时间，审核状态固定为 `PENDING`。无法从锁定枚举诚实映射的来源类型保持空白，而不是自动伪造成其他类别。

## Review Import

仅检查工作簿，不生成正式数据：

```powershell
python scripts/import_review_workbook.py `
  --workbook <本地评审工作簿.xlsx> `
  --candidates <本地候选集.jsonl> `
  --report <本地脱敏报告.json> `
  --validate-only
```

正式导出还必须提供 `--output`、`--dataset-id`、`--embedding-provider`、`--embedding-model`、`--embedding-dimension` 和 `--index-version`。只有 100~200 条记录通过人工批准并满足 Schema 时才会写出文件；不完整或校验失败时不会生成正式集。

实际 Embedding 探测只从环境变量读取 Key，提交报告不含输入文本、向量值或 Secret：

```powershell
$env:PLM_POC_EMBEDDING_API_KEY = '<仅当前会话使用的百炼 Key>'
python scripts/probe_embedding_provider.py `
  --provider aliyun-model-studio-openai-compatible `
  --base-url <对应区域的 OpenAI-compatible Base URL> `
  --model qwen3.7-text-embedding `
  --dimension 1024 `
  --report <本地脱敏探测报告.json>
Remove-Item Env:PLM_POC_EMBEDDING_API_KEY
```

导出后必须执行脱敏覆盖审计；审计报告只包含数量和缺失类别：

```powershell
python scripts/audit_golden_dataset.py `
  --dataset <本地 Golden Dataset.json> `
  --report <本地脱敏覆盖报告.json>
```

## Metrics

|指标|目标|当前状态|
|---|---|---|
|候选评审记录|100~200 条|120 条，26/26 文档覆盖，PASS|
|当前人工批准记录|100~200 条且字段完整|R2 人工填写 120 条 APPROVED；仅 45 条字段完整，75 条缺来源类型|
|本地预填建议|辅助人工评审，不形成真值|120 条不同查询；45 条来源类型可映射，75 条待确认|
|人工确认交互原型|证据可定位、输入有提示、原数据可追溯|R3 生成 120 个本地证据链接；45 条已确认、75 条待补充；PASS_FOR_UX_REVIEW|
|Schema 合法数据集导出|100~200 条|当前 R2 未导出；旧 R1 的 109 条仅 Schema PASS、覆盖 FAIL|
|Gold Set 质量覆盖|查询、四类来源、六类分类可评估|IN_PROGRESS：R2 尚未人工批准，不能审计为正式 Gold Set|
|确定性 Chunk|可追溯且强制 PROJECT/ProjectId|655 个，PASS|
|单索引单 Embedding 模型|不可原地换模/换维度|`qwen3.7-text-embedding` 1024 维 live PASS|
|Top-5 Recall|≥95%|NOT_RUN|
|分类准确率|≥90%|NOT_RUN|
|来源引用准确率|≥98%|NOT_RUN|
|PROJECT 跨项目泄漏|0|NOT_RUN|

## Logs

- 可提交脱敏证据：`evidence/windows-11/`。
- 工作簿结构和操作边界：`review-workbook-spec.md`。
- 候选正文、原始映射和运行输出：`artifacts/poc-03/`，由 Git 忽略。
- 原始方案文件与文件名映射不进入 Git。

## Known Issues

1. 当前方案库只有历史方案类资料，尚不能证明合同、技术协议、调研和标准能力四类覆盖完整。
2. 自动抽取只能形成候选集；没有人工批准的记录不得计入 Golden Dataset，也不得作为业务事实。
3. 两个资料库共 10 个旧版二进制 `.doc` 尚不支持，不进入本轮候选池。
4. Windows Server 2025 与 Debian 13 尚未执行本 PoC。
5. 当前 R2 的 120 条记录已由用户填写为 `APPROVED`，但 75 条 `SOLUTION` 来源在锁定枚举中无对应值，仍不满足正式导出 Gate；必须人工决定、修改正式枚举或补充合适语料，不能自动伪造映射。
6. R3 是本地 UX 原型，不是正式交接待办；当前 Office 原件定位依赖“打开原文件 + 精确定位说明”，正式产品仍需内置证据查看器完成自动跳转与高亮。
7. 旧 R1 的 109 条批准记录只有 1 个唯一查询，且全部为 `SURVEY` / `STANDARD_SATISFIED`，不满足 Gold Set 覆盖要求，保留为历史失败证据。
8. P03-A04 已激活阿里云百炼 OpenAI-compatible `qwen3.7-text-embedding`、1024 维、索引 `v1` 的 PoC 绑定；它不代表正式架构冻结。
9. DeepSeek 官方资料本轮未找到 Embedding 端点；不得把现有 DeepSeek Chat Key 假定为向量服务凭据。

## Conclusion

POC-03 已启动，当前仅形成候选数据准备能力，不形成 RAG 质量通过结论。

## PASS / FAIL

`IN_PROGRESS`

## Alternative

- 如果现有方案库无法覆盖四类资料，保留覆盖缺口，补充脱敏标准能力、合同、技术协议和调研样本后再冻结 Golden Dataset。
- 如果外部 Reranker 不可用，记录失败证据并评估候选外部 API；不得擅自引入本地模型或独立向量库。
