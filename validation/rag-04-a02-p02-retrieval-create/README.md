# RAG-04-A02-P02 Retrieval Create Owner Validation

Windows 11 / PostgreSQL 18.6 合成验收，复用前置的合成 ACTIVE Index，不作为真实业务质量或 Gate 3 证据。

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/rag-04-a02-p02-retrieval-create/verify.py
```

验证范围：

- Session / CSRF / License / 当前项目成员权限 / 当前 ACTIVE Index 失败关闭。
- Job、RetrievalRun、专用 AES-256-GCM QueryContent、Audit 和幂等收据同事务。
- Audit 故障全回滚，同 Key 重放不产生新密文，撤权后重放拒绝。
- Query 明文不进入 Job 或 Audit，密文可用独立密钥端口解密回读。
- 仅支持无外发 `fts.project.v1 + none.v1`；不调用 Provider，不发送客户数据。
