# SOL-05-A04-P01：SectionVersion VALIDATE 前置核查

日期：2026-10-12。结果：`SECTION_VERSION_VALIDATE_PRECHECK_COMPLETE`；未实现或开放 VALIDATE，不能据此宣称方案章节可正式化。

当前 Phase/WBS：Phase 2 / 本 P01。输入：Gate 2 冻结 API-04 的 `SOL_SECTION_VERSION_VALIDATE`，DM-05 的独立不可变章节版本，CR-SOL-003、SectionVersion 0138/0159/0160 Schema/Guard，A02 创建真实来源证明、A03 历史读取与 P06 Windows 11 实际创建页。Gate 2 与前置 CREATE/GET 已验。涉及 Solution/Review/Document/Requirement/Evidence/Trace/StructuredSpec 边界；本项只做只读审计，无 Schema/API/数据改动。

冻结合同为 PM/ImplementationMember POST `/api/v1/projects/{project_id}/solution-sections/{section_id}/versions/{section_version_id}:validate`，控制 S/L/C/I/A，200 返回 evidence/trace/spec report。当前实现检索未发现 SectionVersion VALIDATE 的业务 Owner、可选 HTTP Router 或 Windows 装配；已有 SectionVersion CREATE/历史服务不能代替验证。0160 Guard 仍拒绝四张章节版本表的 UPDATE/DELETE/TRUNCATE，故验证报告不得通过直接修改不可变版本或把 DRAFT 改为 APPROVED。Review 提交是另一个冻结命令，不可由 VALIDATE 偷渡；缺 Spec/Trace/Review 真实证明时不得返回“通过”。

风险与依赖：冻结表格只规定报告类别，未细化字段/快照绑定/幂等回执；需要先形成向后兼容的报告合同和证据状态枚举，绑定固定版本、请求时间与当前来源状态，并区分“结构有效”“来源当前合格”“Trace 覆盖”“StructuredSpec 已可用”“可提交 Review”。已建 Document/Requirement/Evidence 证明可复用，但 StructuredSpec/OutputArtifact Owner 尚未建立，Artifact 分支继续关闭；实际用户确认、正式公钥和服务账户也不能由报告推定。不得因 Spec 缺失静默省略检查或伪造通过，应给明确未就绪结果并保留后续补齐路径。

下一项 `SOL-05-A04-P02`：先定型最小、可追溯的 VALIDATE 报告与幂等/审计合同，明确哪些判断可由现有真实 Owner 完成，哪些只能返回缺项；若须变更冻结路径/角色、核心模型或 0160 DML Guard，则先追加正式 Change Request、迁移/回滚/验证计划。随后分别实现内部 Owner、HTTP/Windows 装配与浏览器/PG 验收。验收应覆盖同项目固定身份、PM/IM 与成员隔离、过期 License、失效正文/Requirement/Evidence、缺 Spec/Trace、同 Key 重放、并发及 Audit 回滚。P01 未运行新程序测试；此前 A03-P06-P03 两轮 Edge/PG exit0 仅证明 CREATE，不证明 VALIDATE。TraceLink：Gate2 API-04/DM-05 → CR-SOL-003/0160 → A02/A03 → 本 P01 → P02/Owner/HTTP/UI → Review → Gate3/Pilot。
