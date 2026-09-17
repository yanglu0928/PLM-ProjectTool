# Phase 0 PoC 规则

## Gate

当前正式开发的唯一前置工作是 Phase 0。阻塞 PoC 全部 PASS 或获得用户确认的替代方案之前，不得大规模开发业务模块。

Phase 0 包含：

|PoC|验证范围|
|---|---|
|POC-01|Python 3.13 在 Windows Server 2025、Debian 13 的核心依赖及离线安装|
|POC-02|PostgreSQL 18 + pgvector、Alembic、HNSW、备份恢复、10 万级向量|
|POC-03|PLM RAG Golden Dataset、Hybrid、Reranker、DeepSeek 与引用质量|
|POC-04|AI Gateway / DeepSeek：文本、流式、结构化输出、超时、重试、错误|
|POC-05|DOCX/PPTX/XLSX/CSV/文本 PDF/扫描 PDF 与 OCR 统一解析|
|POC-06|100 页 Word、50 页 PPT、中文、表格、图片、流程、多级章节|
|POC-08|Plugin Host：崩溃、超时、非法 JSON、不兼容版本、独立升级|
|POC-09|MAC、SHA-256、Ed25519、过期、篡改、错公钥、系统时间|

POC-07 VSDX 为 P1，不阻塞正式开发。

## 每个 PoC 的必需产物

```text
README
Environment
Input
Steps
Result
Metrics
Logs
Known Issues
Conclusion
PASS / FAIL
Alternative
```

任一项缺失，不得判定该 PoC 完成。PoC 结论必须以可重复执行的记录、日志和指标为依据。

## 失败处理

失败时禁止直接更换技术，必须输出：Failure Analysis、Root Cause、Impact、Option A、Option B、Recommendation。只有用户确认后才能修改基线。

## 初始验收门槛

- RAG Golden Dataset 100~200 条。
- Top5 Recall ≥ 95%。
- 分类准确率 ≥ 90%。
- 来源引用准确率 ≥ 98%。
- Plugin 崩溃不得导致 FastAPI 崩溃。
- 非法 License 场景全部拒绝。
- Word/PPT 可由 Microsoft Office 正常打开且文件不损坏。

RAG 指标是初值，只有真实数据 PoC 和评审可修订。

## 推荐执行顺序

Python 依赖 → PostgreSQL/pgvector → Document/OCR → DeepSeek Gateway → RAG → Plugin → License → Word/PPT。

允许在资源具备时并行验证基础依赖、AI Gateway、文档/OCR、Plugin/License、Word/PPT；RAG 端到端验证依赖数据库、AI 和文档链路。

