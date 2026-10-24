# RAG-04-A03-P03 Retrieval Query Preparation Validation

Windows 11 / PostgreSQL 18.6 合成验收，复用前置合成 ACTIVE Index、Retrieval 创建和专属 claim，不作为真实业务质量或 Gate 3 证据。

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/rag-04-a03-p03-retrieval-query-preparation/verify.py
```

验证范围：

- 当前单次 Lease、原请求 Actor ENABLED、当前 Project/Membership/Department 角色与 License 先于密钥读取。
- Run、Job、Project、Actor、Trace、ACTIVE Index/Model、精确来源 Chunk、AVAILABLE Embedding 与 QueryContent 绑定失败关闭。
- AES-256-GCM 解密后严格 UTF-8/NFKC 规范化并复算 query fingerprint。
- 明文只在受权 callback 的 bytearray 中短暂存在，成功或异常后归零。
- 撤销 Membership 或关闭 License 后不读取密钥；无 Provider I/O、无客户数据外发。
