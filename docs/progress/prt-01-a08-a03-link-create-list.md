# PRT-01-A08-A03：RequirementPrototypeLink CREATE/LIST Owner

日期：2026-10-08。结论：`PRT_01_A08_A03_LINK_CREATE_LIST_PASS`。下一项：
`PRT-01-A08-A04` RequirementPrototypeLink REVOKE/SUPERSEDE Owner。

## 实现

- 新增内部 `RequirementPrototypeLinkService` 与 PostgreSQL Repository；CREATE 仅允许
  ProjectManager/ImplementationMember，LIST 对当前项目全部成员开放。授权写策略取得项目/成员锁，列表使用
  锁定读取；本项不开放冻结 HTTP Router。
- CREATE 在同一事务内重证当前 Approved RequirementVersion、当前 Approved PrototypeVersion、批准
  Manifest、PrototypeVersion owned RequirementRef、Prototype 当前输入 Validator 及固定需求全部
  AcceptanceCriterion；Coverage V1 规范化后必须精确分区全集且至少一项 covered。
- Link、Audit 和持久幂等 receipt 同一事务提交；同 Key 重放恢复首次 Link 后重新证明当前端点，逻辑自然重复
  收敛到既有 ACTIVE Link，载荷不同则 `LINK_CONFLICT`。授权、证明、审计或提交失败均不留下半成品。
- LIST 只在当前项目内按 UUIDv7 Link ID 倒序分页，保留 ACTIVE/SUPERSEDED/REVOKED 历史投影；未授权项目按
  既有防枚举合同返回 `RESOURCE_NOT_FOUND`。

## 验证

- Windows 11 / PostgreSQL 18.6 隔离数据库验证真实 Session/CSRF、Project 授权、当前固定双端点、owned ref、
  AcceptanceCriterion 全集、Coverage 分区、同 Key重放、自然重复、冲突、Audit、列表隔离及输入漂移零写入。
  父级复杂批准事实使用合成数据库夹具；本脚本验证 Validator 接线与失败关闭，Validator 自身真实当前事实链
  沿用 A07 的实库证据，不把合成夹具称为客户批准或完整 UAT。
- 首轮负权限断言错误地预期 `PROJECT_ACCESS_DENIED`；核对授权核心后确认非成员按既有防枚举语义返回
  `RESOURCE_NOT_FOUND`，仅修正验收脚本预期，生产授权逻辑未改变，完整重跑通过。
- 新增单元8项；相关定向39项通过；后端全量3165项通过、3项既有环境条件跳过；compileall通过。开发 wheel
  共1216项，SHA-256 `5d5ba5ed4598bb9c382cc9f3f952d12f1683a405d21c7c7eb67a918a7c7d6a0a`，不是正式发行包。

无Migration、公开API、依赖、Secret、客户数据或外发变化；Schema head保持0134。停止装配Service即可关闭
新写入口，既有Link/Audit/receipt不可删除。Server 2025未外推，Debian 13按用户指令跳过；A04生命周期、
A09 HTTP/Windows组合、前端、Workflow、Gate 3、UAT和正式发行仍待。
