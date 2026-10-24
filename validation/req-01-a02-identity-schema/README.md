# REQ-01-A02 Schema0111 验证

在 Windows 11 / PostgreSQL 18.6 隔离临时库执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a02-identity-schema/verify.py
```

验证已有平台数据升级、空 Requirement 历史降级/重升、Alembic drift、Package/Requirement
身份和同项目 membership、项目内规范化编码唯一、状态/正式指针初态关闭、Owner 未安装时禁止
修改/删除/截断，以及存在 Requirement 历史时拒绝物理降级。全部夹具为合成元数据，不读取或外发
项目资料，不创建 RequirementVersion 或正式需求事实。
