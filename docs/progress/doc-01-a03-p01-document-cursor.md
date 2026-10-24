# DOC-01-A03-P01：独立签名 Document 列表游标

日期：2026-09-26；版本：`0.1.0.dev0`；状态：游标与 Windows 当前账户密钥入口 PASS，公开 GET 尚未接线。

按冻结 API-01/02 与 `DEC-20260926-121`，Document 列表游标使用独立 `document-list-cursor-v1` 32 字节 HMAC-SHA-256 密钥，不复用其他列表/上传/License 密钥。载荷只包含版本、资源族、GLOBAL/PROJECT、ProjectId、当前 Session 摘要、page_size 查询指纹及末尾 document_id；规范 Base64URL、常量时间 MAC 校验、字段集/UUID 复算，不含标题、正文、路径。Windows 入口只读当前账户安全密钥引用，缺失或长度错误时失败关闭。

Windows 11/Python 3.13 后端 513 项无失败（2 项符号链接权限跳过）；新增 5 项游标/密钥测试覆盖双 Scope、篡改、跨 Session/Project/Scope/page size、失钥拒绝与临时 Windows Credential Manager 密钥加密备份/恢复旧游标；开发 wheel PASS。无 Migration、公开 API 或新依赖。正式目标账户密钥供给/离线备份、可选 GET、真实数据库分页组合与 Server 2025 尚未完成；不得将单独游标验收外推为 Document 读取可用。
