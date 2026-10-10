# EVD-01-A04-P01：Evidence 资格命令前置核查

日期：2026-10-01；Phase 2 Platform Core；结论：`PRECONDITION_BLOCKED`，不是资格命令 PASS。

编码前检查：输入为冻结 DM-03、API-02、现有 Evidence Candidate/ORM/Session/License/Audit/收据。涉及 Evidence、Document；实体为 Evidence/DocumentVersion/Document；API 为冻结 `EVIDENCE_SET_ELIGIBILITY`，本项未挂载；权限要求项目 PM/受权 CustomerManager 或 GLOBAL DeploymentAdmin，并须人工真实确认。验收为模板非客户事实、当前受权固定来源、幂等/Audit/并发与回滚。风险是来源类别不可在资格事务内通过 Document Port 证明，且模板用途尚无 Binding 上下文。

决定：先按 CR-EVD-003 补内部 Document 同事务来源事实 Port，再做资格规则与写入；本项仅前置核查。原有 Evidence 创建/读取/Viewer 不受此阻塞。正式客户事实、Gate 3 和可用程序包未通过。
