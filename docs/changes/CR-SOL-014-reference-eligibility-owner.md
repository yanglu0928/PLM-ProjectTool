# CR-SOL-014：ReferenceSolution 资格状态受控确认

日期：2026-10-09；状态：`WINDOWS_COMPOSITION_PG_PASS_UI_CONTRACT_PASS_BROWSER_PENDING`（A16-P05 Windows 显式写组合/真实 PG 已验，P06-P01/P02 前端合同/组件通过；默认与只读组合未挂载，Edge/真人确认待验）。依据 CR-EXEC-001 持续授权先记录后实施；Gate 2 原冻结提交 `64cdf09` 保留。TraceLink：API-04/DM-05 → CR-SOL-004/005/007、0139～0153 → SOL-01-A05/A14 → 本 CR。

## 来源、冲突与选择

冻结 `SOL_REFERENCE_SET_ELIGIBILITY` 要求 PROJECT ProjectManager 或 GLOBAL DeploymentAdmin 对参考身份作人工资格决定并记录原因。0139 根已有 `REFERENCE_ONLY/ELIGIBLE/RESTRICTED/REVOKED` 与 reason，但 0144 Guard 禁止根 UPDATE；当前 GET/LIST 只反映历史 `REFERENCE_ONLY`，不能证明“现时合格”。直接把 DRAFT 参考版本或来源存在性推断为 ELIGIBLE 会绕过当前 Document/Evidence、Scope/Project 和 GLOBAL 脱敏证明；开放任意根 UPDATE 则会破坏身份/当前版本完整性。

选择独立于修订的受控状态命令：仅修改根 `eligibility_state`、`eligibility_reason`、`lock_version`，当前版本指针/身份不随资格命令改变；ELIGIBLE 前同事务复验当前版本固定来源、实时 Document/Evidence 资格与 GLOBAL 人工脱敏确认，非 ELIGIBLE 状态仍保留原因、操作者和审计。AI 建议不能成为资格决定；实际授权人工命令是正式事实。结果不明时同幂等 Key 重放原 200，而非返回之后变化的状态，建立不可变资格结果快照。

## A16-P01 状态机与修订失效规则

|原状态|允许的人工目标|禁止/处理|
|---|---|---|
|REFERENCE_ONLY|ELIGIBLE、RESTRICTED、REVOKED|自环不产生新事件；只能人工作出首次决定|
|ELIGIBLE|RESTRICTED、REVOKED|不得用同一旧资格记录直接维持新版 ELIGIBLE|
|RESTRICTED|ELIGIBLE、REVOKED|重新 ELIGIBLE 必须重新证明当前来源及 GLOBAL 确认|
|REVOKED|无|终态；不得通过修订或新 Key 恢复资格|

非初始人工决定必须有规范化非空原因、操作者、当前 `reference_version_id`、前后状态和审计；项目 ProjectManager / GLOBAL DeploymentAdmin 之外不得决定。任何状态变化使根锁版本递增一次；相同 Key/完全相同请求返回首次 200 的不可变响应快照，其他 Key/If-Match 必须与实时根锁版本比较。版本不变、来源日后失效时旧事件只是历史，不表示现时可复用；消费方仍须做实时资格与版本绑定核验。

**发现并纳入本 CR 的偏差**：现行 `revise_reference_solution.py`/0150 Guard 在修订时保留 `ELIGIBLE`，会使旧版本的人工作决定表面延续到新版本，与“现时合格”冲突；A14 曾要求修订不自动改变资格，此处按用户持续变更授权明确以保守失效规则取代。修订 `ELIGIBLE` 根时，同事务只可自动降为 `RESTRICTED`、写固定系统原因 `CURRENT_VERSION_CHANGED_REQUIRES_REVIEW`、事件/Audit 记录 `SYSTEM_INVALIDATION`，新版本需再由合格人工设为 ELIGIBLE。其他状态修订时保持原状态；REVOKED 始终终态。系统失效不能当成人工授权或新资格。修订首次结果及重放 ETag 继续取真实 `result_lock_version`；不改 `/api/v1` 路径/角色/字段。若迁移与现有修订结果闭合冲突，禁止先放宽 Guard 或静默保留 ELIGIBLE，先在测试中证明原首次结果、历史结果和锁版本闭合。

迁移应新增不可变资格事件/首次响应快照，约束 Scope/Project/当前版本/状态/原因/锁版本连续性；扩展根 Guard 仅接受资格命令的受限更新，或上述修订失效的受限联合更新。不能把只读历史根状态回填成已有人工作决定；既有 ELIGIBLE 但无可信版本绑定的历史应拒升并要求可审计前向修复。降级只能在无资格事件/结果且无新 Guard 依赖历史时执行；有历史拒降并保留数据。Guard 防普通直接 UPDATE/DELETE/TRUNCATE，但不声称能抵御数据库 Owner/Superuser 或代替应用内现时来源证明。

## 差异、影响、迁移/回滚与验证

**A16-P03 新发现的前向修复**：0152 事件 CHECK 曾将 `prior_lock_version` 设为 `>=1`；正常首次 Reference 根初始 `lock_version=0`，故若直接开放 Owner 会拒绝第一笔人工资格决定。保留已发布 0152 历史，由 0153 明确把下界改为 `>=0`（结果仍须 `prior+1`），同步 ORM 并用真实首版根 `v0→v1` 与有历史升级、降级约束恢复验证；不得通过伪造初始锁或手工改客户数据绕过。0153 降级只在无资格历史时恢复 0152 原约束。

此 CR 只实现冻结资格操作及修订资格保守失效，不改冻结 `/api/v1` 路径、角色或 Scope；需 ORM、新线性迁移的受限 Guard/事件/结果快照、up/down、空库与有数据升级、已有资格历史拒降。未经真实 Owner/Guard 同单元验证不得开放根 UPDATE；回滚优先撤下可选路由/关闭写入，历史保留并向前修复。资格命令只可针对已存在且来源当前性已被证明的版本，不能以历史修订结果代替验证。

必测 PROJECT/GLOBAL 授权与跨项目隐藏、REVOKED/RESTRICTED 负例、当前来源撤回与重新核验、GLOBAL 确认指纹/操作者/有效性、并发版本/同 Key 重放、Audit/Receipt 同事务回滚、直接 SQL 越权 UPDATE/DELETE/TRUNCATE、License/Session/CSRF、默认关闭及 Win11 隔离 PG。HTTP/Windows/UI/浏览器和正式目标账户/Server2025/20 并发分别验收；未取得证据前不标 PASS。

## A16-P06 前端兼容差异（实施前登记）

前端 PROJECT/GLOBAL 详情客户端当前 `eligibility_reason` 校验上限为 1000 字；0139 Schema 与 A16-P03 状态机允许 1～2000 字。若人工输入合法的 1001～2000 字理由，后端可成功写入但详情客户端会拒绝整个当前态。这是读取客户端和既有正式数据合同的偏差，不应收窄已允许的服务端值或截断审计事实。选择将两个详情解析上限对齐为 2000 字，并在 A16-P06 单测覆盖 2000 接受、2001 拒绝；不修改 DB/迁移、服务端 API 或已有历史。回滚为撤前端改动，但会重新暴露详情读取失败；因此先验证再合入。
