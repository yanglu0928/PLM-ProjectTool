# SOL-05-A02-P02：SectionVersion PROJECT Document 正文证明适配器

日期：2026-10-09。结果：`SECTION_DOCUMENT_CONTENT_PROOF_INTERNAL_PASS`；仅内部端口/单元回归，未创建 SectionVersion。

## 编码前检查

Phase 2 Platform Core；输入 Gate2 DM-05/API-04、CR-SOL-003/0138、SOL-05-A02-P01、Document 现有固定版本身份锁与 `DocumentFixedSourceProofService`；前置满足。单一问题是确保未来 SectionVersion DRAFT 的 `content_document_version_ref` 不是裸 FK，而能在调用者事务中证明同项目 DocumentVersion 可读、文件字节/大小/Hash 可用。涉及 Solution→Document Application Port，不改 Document 业务服务、Schema/API/权限。验收包括同事务 PROJECT 身份、原 Session 授权、物理证明、归属/摘要验证和错项目/失效/异常失败关闭；风险是把“可用文件”误称经审核的章节正文。

## 实施与验证

新增 `SectionDocumentContentProof` 不透明 DTO/Port 与 `SectionDocumentContentProofAdapter`。先用 Document-owned 固定版本身份查找并锁定 PROJECT 同项目 Document/Version，再以同一事务和原 Session 调用通用固定来源服务；仅接受 PROJECT、同 ID、ACTIVE Document 与规范 SHA-256，返回 Project/Document/Version ID 和摘要，不返回正文、Locator 或管理员视图。错 Scope/项目/版本、归档、坏 digest、底层异常均统一失败关闭。Document 类别语义与章节正式内容审批仍留给后续 Owner/VALIDATE，不复用 ReferenceSolution 特有的类别白名单；Artifact 分支仍无写入证明。

定向 pytest `5 passed, 16 subtests passed`，覆盖同事务、身份/权限传递、错误输入、跨项目/归档/坏摘要及异常清理投影；后端全量 pytest `3507 passed, 3 skipped, 5439 subtests passed`、退出0。测试使用 stub 验证本适配器合同；Document 通用物理服务已有独立验证，本项**未**做 SectionVersion 实际 PG 写入、浏览器或正式服务账户验收，不将本单元结果扩大为端到端 PASS。

兼容性/升级/回滚：仅新增未接线内部模块和单元测试，无 Migration、公开 API、权限、配置、依赖或数据变化；撤本适配器可回滚，0138 闭锁及历史不动。下一项 `SOL-05-A02-P03` 对固定 RequirementVersion 建同项目当前批准证明；随后再做 Evidence、Section 当前基底与受控 Owner/Guard。Server2025/正式信任、性能、质量和 Gate3/发行仍未通过；Debian13实机依用户指令跳过。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-003/0138 → SOL-05-A02-P01 → DEC-1168 → 本证明 → SectionVersion Owner/Guard → VALIDATE/Review/Trace → Gate3。
