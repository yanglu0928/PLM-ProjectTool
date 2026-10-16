# SUR-04-A05：SurveyConclusion 来源、冲突与完整性校验

日期：2026-10-07。结论：`SUR_04_A05_CONCLUSION_VALIDATION_PASS`。下一项：
`SUR-04-A06` 接入 `SRV-05 + SURVEY_CONCLUSION_ALL_V1` Review Subject、原子送审和终态消费。

## 编码前检查与范围

- 依据冻结 API-04、CR-SUR-009、Migration0109 和 DEC-958/959，只实现内部 VALIDATE Owner；不开放
  HTTP、Review、Workflow、正式范围排除或风险接受写入。
- 注册冻结 `SURVEY_CONCLUSION_VALIDATE` Project 授权，限 PROJECT_MANAGER 与
  IMPLEMENTATION_MEMBER；未提前注册 SUBMIT_REVIEW。
- 校验只写 Audit 和持久幂等 receipt，不修改 Conclusion 状态或其不可变正文；同键重放返回原始时点
  报告，新键才重新观察当前事实。
- 无 Schema、Migration、公开 URL、第三方依赖、Secret、客户数据外发或 AI 调用变化。

## 实现

- 在调用者事务内锁定 Conclusion、CLOSED Round 与四张 owned 表，并重新证明 VALIDATED 链尾
  Response、当前 PROJECT_RECORD、HND-03 当前状态及当前 Invocation 绑定的 SUCCEEDED
  SURVEY_ANALYZE provenance。
- 服务器按稳定次序报告内容指纹/计数、Round/Response/Evidence/AI/open issue 不可用、CONFLICT、
  未关闭阻断待办、无支持来源及未受权正式决定。任何 CONFLICT 或未关闭关键待办均失败关闭；AI 仍为
  `NOT_FORMAL_FACT`，不能作为支持来源或放行依据。
- 原始创建指纹用不可变 owned 快照重建；HND-03 后续自然关闭按当前事实解除阻断，不被误报为正文
  篡改。Evidence 撤销、版本/lock/fingerprint 漂移立即报告 `EVIDENCE_UNAVAILABLE`。
- Audit reason code 以有界字母位图和四项观察计数保存，因此幂等重放无需再次读取易变来源，也不会把
  后续事实冒充原报告。

## 验证

- 定向 14 项通过，覆盖有效来源、冲突/阻断、来源漂移、内容指纹、计数、未受权决定、Secret 脱敏、
  Audit/receipt、重放和 Project 授权矩阵。
- Windows 11 / PostgreSQL 18.6：OPEN 阻断、关闭后新键重验 PASS、同键保留原 BLOCKED、Evidence
  撤销后失败、Session/CSRF/License/角色、Audit 故障回滚恢复、Audit/receipt 数量、状态始终 DRAFT
  及 Alembic drift 全部通过；临时数据库已删除。
- 后端全量 `2930 passed / 3 skipped`。开发 wheel 1100 项并包含三个 A05 运行模块，SHA-256
  `56f87223d2a615e9aa29421320a5d09b3c7656bda80bcf4ea73a1be72618e465`；不是最终可使用程序包。

已知未完成：A06 Review、SUR-05 HTTP/UI、SUR-06 Workflow 资格、Windows Server 2025、Gate 3、
UAT 和发行包。
