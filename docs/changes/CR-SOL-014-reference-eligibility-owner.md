# CR-SOL-014：ReferenceSolution 资格状态受控确认

日期：2026-10-09；状态：`PLANNED_NOT_IMPLEMENTED`。依据 CR-EXEC-001 持续授权先记录后实施；Gate 2 原冻结提交 `64cdf09` 保留。TraceLink：API-04/DM-05 → CR-SOL-004/005/007、0139～0144 → SOL-01-A05 → 本 CR。

## 来源、冲突与选择

冻结 `SOL_REFERENCE_SET_ELIGIBILITY` 要求 PROJECT ProjectManager 或 GLOBAL DeploymentAdmin 对参考身份作人工资格决定并记录原因。0139 根已有 `REFERENCE_ONLY/ELIGIBLE/RESTRICTED/REVOKED` 与 reason，但 0144 Guard 禁止根 UPDATE；当前 GET/LIST 只反映历史 `REFERENCE_ONLY`，不能证明“现时合格”。直接把 DRAFT 参考版本或来源存在性推断为 ELIGIBLE 会绕过当前 Document/Evidence、Scope/Project 和 GLOBAL 脱敏证明；开放任意根 UPDATE 则会破坏身份/当前版本完整性。

选择独立于修订的受控状态命令：仅修改根 `eligibility_state`、`eligibility_reason`、`lock_version`，当前版本指针/身份不随资格命令改变；ELIGIBLE 前同事务复验当前版本固定来源、实时 Document/Evidence 资格与 GLOBAL 人工脱敏确认，非 ELIGIBLE 状态仍保留原因、操作者和审计。AI 建议不能成为资格决定；实际授权人工命令是正式事实。结果不明时同幂等 Key 重放原 200，而非返回之后变化的状态，必要时建立不可变结果快照。历史资格事件及不可逆 REVOKED 语义须在详细状态机设计中定稿，不凭推断放宽。

## 差异、影响、迁移/回滚与验证

此 CR 只实现冻结资格操作，不改冻结 `/api/v1` 路径、角色或 Scope；需细化 ORM、新线性迁移的受限 Guard/结果快照、up/down、空库与有数据升级、已有资格历史拒降。未经真实 Owner/Guard 同单元验证不得开放根 UPDATE；回滚优先撤下可选路由/关闭写入，历史保留并向前修复。若修订仍未通过，资格命令只可针对已存在且来源当前性已被证明的版本，不能以修订计划代替验证。

必测 PROJECT/GLOBAL 授权与跨项目隐藏、REVOKED/RESTRICTED 负例、当前来源撤回与重新核验、GLOBAL 确认指纹/操作者/有效性、并发版本/同 Key 重放、Audit/Receipt 同事务回滚、直接 SQL 越权 UPDATE/DELETE/TRUNCATE、License/Session/CSRF、默认关闭及 Win11 隔离 PG。HTTP/Windows/UI/浏览器和正式目标账户/Server2025/20 并发分别验收；未取得证据前不标 PASS。
