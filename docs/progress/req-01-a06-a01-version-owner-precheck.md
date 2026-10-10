# REQ-01-A06-A01：RequirementVersion create/list/get 编码前核查

日期：2026-10-07。结论：`REQ_01_A06_A01_VERSION_OWNER_PRECHECK_PASS`。下一项：
`REQ-01-A06-A02` RequirementVersion 原子创建 Owner 与数据库写边界。

## 冻结合同与现状

- 冻结API提供项目内 Version create/list/get；创建者为 ProjectManager、ImplementationMember，读取者为
  Project member；创建结果只能是完整不可变 DRAFT。
- `VersionCreateRequest`要求`base_version_ref`或`initial`、完整内容快照、Evidence/Trace输入引用和原因；
  RequirementVersion最小内容为statement/rationale、domain/priority/risk、classification、能力判断、来源、
  验收标准、assumptions/exclusions/dependencies。
- Migration0116～0118已物理化Version、六类owned表和三类支持引用，但全部业务写Owner仍关闭；延迟完整性
  触发器要求主行、声明计数、连续ordinal、Evidence scope和AI accepted-to-draft在提交时一次闭合。
- A05已提供批准Survey、当前Handover、不可变Human Decision、当前PROJECT Evidence和当前GLOBAL
  Capability的调用方事务proof；A06不得跨模块复制状态判断。

## 实施拆分与决定

1. A02开放原子创建：锁定ACTIVE Requirement和当前最高版本；首版必须显式`initial=true`且无历史，或
   `base_version_ref`精确等于当前最高版本。创建同时将Requirement ETag递增一次，阻止并发分叉。
2. A02在同一事务逐项调用A05来源proof和Evidence/Capability proof，写入完整Version/owned/support集合、
   Audit、Idempotency receipt及不可变首响应；任何proof、Audit或闭包失败均整体回滚。
3. A03实现授权list/get；列表按`version_no`稳定keyset，只返回不可变版本摘要；get返回精确Version及完整
   有序集合，固定引用不解析为current/latest，不暴露locator、正文或数据库实现字段。
4. 内容指纹使用完整规范化业务快照，不包含会随事务变化的actor/time/version_no/数据库行ID；同一内容与
   固定引用产生稳定SHA-256，重放必须与首次指纹一致。
5. 当前AI Task要求在同一Version ID上已`ACCEPTED_TO_DRAFT`，而冻结create未提供客户端Version ID或已定义
   的跨Owner预接纳协议。首版创建只接受空AI Task集合；后续必须以独立CR建立可原子证明的接纳协议，不能
   通过管理员更新或忽略0118闭包伪造provenance。

## 验收与回滚

- A02需新增Migration开放最小INSERT/Requirement ETag更新，并验证空库/历史库升降、drift、并发、幂等、
  Audit回滚、五类来源、Evidence scope和闭包负例；有Version历史继续拒绝物理降级。
- A03需验证项目隔离、全部项目角色读取、非成员拒绝、keyset无重漏、完整有序投影和零写。
- 本项纯文档，无Schema、Migration、程序、依赖、Secret、客户数据或外发变化；A02前Version Owner仍关闭。
