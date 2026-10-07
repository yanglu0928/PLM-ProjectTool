# SUR-04-A03：SurveyConclusion 类型化来源 proof adapters

日期：2026-10-07。结论：`SUR_04_A03_CONCLUSION_SOURCE_PROOFS_PASS`。下一项：
`SUR-04-A04` Conclusion create/list/get Owner。

## 编码前检查与范围

- 依据 CR-SUR-009、Migration0109 与冻结 SRV-05，只建立四类只读、调用者事务内的最小证明：
  VALIDATED Response、PROJECT_RECORD Evidence、HND-03 Action 和 SUCCEEDED SURVEY_ANALYZE Task。
- 各事实仍由所属模块读取和锁定；Survey 只消费类型化 proof，不读取 Document、Evidence、Handover 或
  AI 私有 ORM，不提交事务，也不创建 Conclusion、客户事实或风险接受。
- 无 Schema、Migration、公开 API、第三方依赖、Secret、客户数据外发或 AI 调用变化。

## 实现

- Survey Response proof 固定同 Project/Survey/所选 CLOSED Round 的 VALIDATED Assignment 当前链尾，
  返回 Answer、Department、Question、Evidence ID 集合及规范答案指纹；旧更正节点和空/错父资源拒绝。
- PROJECT_RECORD adapter 复用 Evidence/Document Owner，限定 ProjectManager/ImplementationMember、
  `PROJECT + ELIGIBLE + PROJECT_RECORD`，只返回固定 DocumentVersion、Evidence lock/content fingerprint
  与证明人。
- Handover adapter 将 HND-03 Action 与其 `lock_version` 对应的当前 state event 一并只读锁定，防止
  使用过期状态快照。
- AI adapter 仅接受同 Project、SUCCEEDED `SURVEY_ANALYZE` 的当前 Invocation-bound SuggestionPayload；
  `AVAILABLE/ACCEPTED_TO_DRAFT` 均保持 `NOT_FORMAL_FACT`，只作为 provenance，不成为批准事实。

## 验证

- 新增 3 项单元测试，覆盖最小投影、Secret/指纹不进入 repr、类别/角色/scope/state/identity/shape
  失败关闭与依赖异常归一化。
- Windows 11 / PostgreSQL 18.6 一次性数据库：真实 Migration head/drift、四类当前 proof、同事务只读锁、
  跨项目、错 Round、缺失引用、未授权角色拒绝以及调用前后五类表计数不变全部通过；临时数据库已删除。
- 后端全量 `2917 passed / 3 skipped`；最终开发 wheel 1093 项并包含六个新模块，SHA-256
  `70d6e5f9c6d18b7f01d5ab4506075bd746f11e3c2a3d891c5b174a16f7643de8`。它仅用于开发验证，
  不是最终可使用程序包。

已知未完成：A04 create/list/get、A05 Validate、A06 Review、SUR-05 HTTP/UI、SUR-06 Workflow资格、
Windows Server 2025、Gate 3、UAT 和发行包。
