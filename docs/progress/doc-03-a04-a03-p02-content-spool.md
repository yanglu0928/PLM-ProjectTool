# DOC-03-A04-A03-P02 有界流式 Content 校验与受控暂存

日期：2026-09-25；结果：内部 Storage 子任务 PASS，完整 Content 命令/HTTP 尚未实现。追溯：冻结 API-02 `DOCUMENT_UPLOAD_CONTENT`、DM-03 上传次序、ADR-008、DEC-20260925-103。

在 Document 模块增加受控单次暂存器。调用者提供已授权的 Scope/Project 与内部 FileObject UUID、文件显示名、声明长度与 SHA-256，以及按部署/业务用途注入的格式允许清单；暂存器不接受物理路径。以独占模式写入临时 Locator，单块不超过 1 MiB，写入中检查上限并同步计算 SHA-256，最终比对长度/摘要。文件类型不信任扩展名或 MIME hint：PDF 检查头/尾特征，OOXML 检查 ZIP 容器、路径、条目数、展开总量、CRC 和主部件 Content Type，PNG/JPEG/TIFF 检查基本签名，UTF-8 文本/CSV 拒绝控制字符。未列入允许清单的格式失败关闭；类型识别不是病毒扫描或完整解析。

校验失败时只在路径仍指向本次创建的普通单链接文件且设备/inode 相同时删除暂存文件；身份变化或删除失败则不触碰未知文件，留后续 TTL 恢复/清理机制。成功仅返回相对 Locator、Hash、Size、detected MIME 证明，不建立 FileObject、DocumentVersion 或 Parser Job；故不能从本入口访问业务内容。后续数据库登记必须重新核验 Intent 过期/创建者/Token/Scope 和物理文件身份，处理重复 PUT、并发、崩溃及孤儿文件，不得把本子任务等同于完整上传。

Windows 11/Python 3.13：新增 6 项真实临时文件系统测试覆盖 PDF、DOCX/XLSX/PPTX、图片、文本、大小/Hash/MIME、ZIP 路径、文件名、重复写入和身份保护；后端合计 470 项无失败，2 项符号链接权限场景跳过。开发 wheel 构建通过。无 Migration、公开 API、新依赖或生产组合变动。Windows Server 2025/Debian 13、正式权限和最终程序包仍未验证。
