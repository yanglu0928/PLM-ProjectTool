# CR-DOC-004：三步上传的 UploadIntent 持久层增量

日期：2026-09-25；状态：按 CR-EXEC-001 持续授权，DOC-03-A04-A01 Schema 增量已实施并验证。范围：Phase 2 / DOC-03-A04-A01。

## 来源与冲突

Gate 2 冻结 API-02 已明确 `DOCUMENT_UPLOAD_CREATE/CONTENT/COMMIT/ABORT` 四个操作和 UploadIntent→流式 Content→幂等 Commit 协议；当前正式 Schema head `20260925_0022` 仅有 Document、DocumentVersion、FileObject，缺少能保存上传创建者、Scope/Project、用途、新建/升版目标、短时 Token 摘要、过期和状态的 UploadIntent。FileObject 是内容元数据，不应承担会话令牌/意图状态，且仅靠内存记录无法跨进程重试或崩溃恢复。原冻结提交 `64cdf09` 保留不改。

## 方案比较与选择

- 不选把上传令牌/表单字段塞入 FileObject：破坏内容身份与临时命令生命周期分离，容易把未完成上传当成内容对象。
- 不选内存或普通临时 JSON：无法跨进程重试、过期检查、并发幂等和审计恢复。
- 选择独立 `doc_upload_intents` 表，作为 Document 模块内部短生命周期控制 Root：绑定 Scope/Project、创建者、目标 Document 或新建元数据、用途/大小/MIME 提示、短时 Token 摘要、状态/过期/版本与可选 FileObject 引用；Token 原值不入库。文件内容仍只在受控 Storage Adapter 中，正式版本仍由 DOC-02 提交。

## 差异、迁移与回滚

这是冻结 API 所需、但冻结数据模型/物理 Schema 未显式列出的内部 Root 增量；不改变公开路径/DTO、技术栈或原冻结语义。新增 ORM 与 Alembic `20260925_0023`，目标库先备份再升级。空意图表允许普通降级，有记录时拒绝降级并保留追溯；历史 Document/FileObject/Version 不倒写。无新依赖。

## 验证与剩余风险

PostgreSQL 18 临时库已验证已有 Document 数据升级、空意图表降级/再升级、ORM 差异为零、PROJECT Scope/目标归属、令牌摘要唯一与长度、状态/文件/版本关联、合法提交、非法状态/身份变更、DELETE/TRUNCATE 和非空降级保护；Windows 11/Python 3.13 后端 462 项无失败（2 项符号链接场景因账户权限跳过），开发 wheel PASS。并发唯一性主要由数据库唯一约束保证，尚无专门负载测试。后续独立完成受权 Create、流式 Content、Commit/Abort、Token 过期与重传、Parser Job/Outbox、Windows Server 2025 与发行演练。Schema 增量不等于三步上传已可用，Gate 3 不因此放行。
