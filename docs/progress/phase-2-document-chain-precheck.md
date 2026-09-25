# Phase 2 Document 链前置核查与 WBS 分解

- 当前 Phase：Phase 2 Platform Core；当前 WBS：Document/Evidence/Workflow/Review/Trace 前置核查。
- 输入基线：Gate 2 冻结 Architecture、DM-03、SC-01/02/03、API-01/02；PRJ-04-A16-P03、Auth、Audit、License 已完成的内部/平台入口。
- 现状：正式代码尚无 document/evidence/workflow/review/trace 模块；Schema 至 Migration `0019`，不含这些 Root。PoC 解析结果不能替代正式受权 DocumentVersion、Evidence 或 TraceLink。
- 依赖顺序：DOC-03 FileObject 元数据/状态事件与受控 Storage Adapter → DOC-01 Document 身份/授权 → DOC-02 不可变版本与文件绑定 → 上传 Commit/恢复/下载 → DOC-04 ParseRecord/Job；Evidence 依赖固定 DocumentVersion 与可复现 Locator；Trace 依赖受控 Object/Version Port；Review/Workflow 依赖业务对象和证据快照。
- 首个单问题任务：`DOC-03-A01 FileObject 持久层`，见 CR-DOC-001；不在该任务开放文件 HTTP，也不把数据库表等同可用文件服务。
- 权限：未来 PROJECT 数据须逐次校验 ProjectId 与当前角色；GLOBAL 只由明确授权入口读取/写入。FileObject 自身不直接暴露 Locator 或公共静态 URL。
- 验收：Migration/ORM、Scope/Project、状态/Hash/大小/Locator 约束、状态历史不可变、空库和已有数据升降级及保护；下一任务单独验证实际文件系统安全边界。
- 风险：FileObject 与文件系统无分布式原子事务；Job 在实施方案 Phase 3，但 Phase 2 Document 上传提交需要 Parse Job。先完成无跨 Phase 依赖的元数据/Storage/Document/Version，Job 前置到可用上传闭环前再以 Change Request 记录时序偏差，不伪造完整 Document 功能。
