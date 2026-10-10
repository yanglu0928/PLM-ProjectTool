# RAG-04-A02-P01 Schema0088 验证

在 Windows 11 / PostgreSQL 18.6 隔离临时库执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/rag-04-a02-p01-retrieval-schema/verify.py
```

验证空/已有基础数据升级、空历史降级与重升、Alembic drift、六张 RAG-04 表、QueryContent 只有密文形状，以及有 RetrievalRun 历史时拒绝物理降级。脚本不发起 Provider I/O，不使用客户数据；历史拒降夹具通过 PostgreSQL `replica` 模式仅向用后即删临时库写入合成占位引用。
