# SUR-04-A04：SurveyConclusion create/list/get Owner

日期：2026-10-07。结论：`SUR_04_A04_CONCLUSION_CREATE_READ_PASS`。下一项：
`SUR-04-A05` source/conflict/completeness Validate Owner。

## 编码前检查与范围

- 依据冻结 API-04、CR-SUR-009、Migration0109 和 DEC-958，只实现内部 CREATE/LIST/GET Owner、仓储与
  投影；不开放 HTTP、Review、Workflow 或正式决定写入。
- 注册冻结 `SURVEY_CONCLUSION_CREATE/LIST/GET` 三项 Project 授权：PM/ImplementationMember 创建，
  全部当前 Project member 读取；未提前注册 A05/A06 操作。
- 无 Schema、Migration、公开 URL、第三方依赖、Secret、外发或 AI 调用变化。

## 实现

- CREATE 统一执行 Session/CSRF、License、当前 Project 授权、持久幂等、Audit 和最终 License 重检；
  新 series 从 v1 开始，后继只接受同 Project/Survey/series 的精确最新版本并连续升版。
- 固定锁序为 series → Survey/CLOSED Rounds → VALIDATED Response → HND-03 → PROJECT_RECORD Evidence
  → AI Task；同类引用按 UUID 稳定排序后证明，避免不同请求顺序形成锁反转。
- Root、部门/模块结论、Evidence 与 open issue 在同一事务形成完整不可变快照。部门 Response 必须属于
  对应部门；Evidence 固定 DocumentVersion/lock/fingerprint；AI 只保存非正式建议 provenance。
- 首版输入不提供 `SCOPE_EXCLUSION/RISK_ACCEPTANCE` 字段，所有决定列保持 NULL；不存在正式决定 Owner
  时不能借创建命令解除冲突或缺失。
- LIST 按 `(created_at, survey_conclusion_id)` 稳定倒序分页，只返回版本摘要；GET 返回固定 Round、AI、
  Department/Module、Evidence 和 HND-03 快照，不读取或复制跨模块正文与路径。

## 验证

- Conclusion 定向 13 项和 Project policy 断言通过；覆盖结构/Secret、proof 形状、部门归属、原子
  Audit/receipt、幂等重放、严格列表位置与缺失详情失败关闭。
- Windows 11 / PostgreSQL 18.6：PM/Implementation 创建、同键并发、冲突幂等、Audit 故障回滚恢复、
  v1→v2 连续 series、旧父版本拒绝、五版本三页读取、详情快照、跨项目隐藏、成员撤权、零正式决定列和
  drift 全部通过；临时数据库已删除。
- 后端全量 `2923 passed / 3 skipped`。开发 wheel 1097 项并包含四个 A04 模块，SHA-256
  `37efc361153d9829801b265669128b9c1c022b44532d9a88453efe990ed61adb`；不是最终可用程序包。

已知未完成：A05 Validate、A06 Review、SUR-05 HTTP/UI、SUR-06 Workflow资格、Windows Server 2025、
Gate 3、UAT 和发行包。
