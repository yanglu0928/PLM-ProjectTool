# RAG-04-A06-P03 Retrieval Read Owner 验证

在 Windows 11 / PostgreSQL 18.6 临时数据库中复用真实 RAG Retrieval Worker 生成的成功结果，验证：

- 创建者与受权监督角色可读取安全 Run、Result 和最小 Context 投影；
- 当前 Session、License、Project membership 在同一读取事务中复验；
- 普通非创建者、错误 Project、已撤销 membership 均按资源不存在失败关闭；
- Result/Context 逐次复验当前 Document、DocumentVersion、Chunk 状态与 Project 绑定；
- 公开投影不返回 query 原文/密文、向量、Golden 标签、人工答案或其他项目存在性。

运行：

```powershell
$env:PYTHONPATH='apps/backend/src'
& .\.poc-runtime\poc-01\windows-online\Scripts\python.exe `
  validation/rag-04-a06-p03-retrieval-read-owner/verify.py
```

成功标记：`RAG_04_A06_P03_RETRIEVAL_READ_OWNER_PASS`。
