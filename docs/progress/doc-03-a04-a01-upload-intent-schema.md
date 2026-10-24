# DOC-03-A04-A01 UploadIntent 持久层

日期：2026-09-25。版本：`0.1.0.dev0`。状态：Schema/ORM 子任务 PASS；三步上传整体未实现。

依据冻结 API-02 和 CR-DOC-004，新增 Document 私有 UploadIntent Root：上传身份、Scope/Project、创建者、已有/新建 Document 意图字段、用途与大小/MIME 提示、仅摘要形式的短时 Token、过期、状态、可选 FileObject/提交结果及版本。数据库约束与触发器守护跨 Scope 归属、Token 唯一和长度、CREATED→CONTENT_READY→COMMITTED 或终止状态的合法流转、版本结果归属与身份不可变；DELETE/TRUNCATE 拒绝，非空历史不得普通降级。

Windows 11/Python 3.13 后端 462 项无失败（2 项符号链接场景因账户权限跳过）；PostgreSQL 18 临时库已有 Document 数据升级、空表降级/再升级、ORM 差异、合法/非法状态及归属、Token、历史保护 PASS；开发 wheel PASS。新增 Migration `20260925_0023`，目标库须先备份后升级至 head。无公开 API 或新依赖。

当前仅是控制元数据，尚不能创建上传意图、接收正文或提交版本；正式 Session/Project/License 授权、Token 生命周期、上传大小/类型/文件特征检查、文件恢复、Parser Job/Outbox、Server 2025/Debian 13 与最终程序包均待。追溯：`CR-DOC-004`、`DEC-20260925-100`、API-02、冻结 DM-03、`validation/doc-03-a04-a01-upload-intent-schema/verify.py`。
