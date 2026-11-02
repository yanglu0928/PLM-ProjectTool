# OUT-01-A01-P02：OutputRequest 原子创建与幂等 Owner 编码前检查

- 日期：2026-11-02
- 状态：PRECHECK_COMPLETE / READY_TO_IMPLEMENT（内部 Owner；不接公开HTTP）
- Phase/WBS：Phase 2 / OUT-01-A01-P02
- 输入：`OUT-01-A01-P01`、CR-OUT-001、冻结 API-03、DM-04、现有 Jobs/Outbox、Audit、Project Authorization 与通用 Idempotency receipt 基础
- 计划验证：GitHub hosted Windows Server 2025 runner 的D盘临时目录与临时 PostgreSQL 18；不在用户本机运行

## 目标和单一问题

实现 OutputRequest 的首次持久创建在并发、重试和事务失败下保持单次且可追溯：只在一次事务中建立已授权固定 ContextSnapshot、OutputRequest、OUTPUT Job/Outbox、Audit 与幂等回执；相同请求重放同一请求/Job引用。该项只打通内部 Application Owner 和Jobs enqueue Port，不实现 HTTP、Plugin Execution、Artifact、文件生成、公开业务事实或前端。

## 编码前检查

|检查|证据与结论|
|---|---|
|当前状态|STATUS 下一项为本 WBS；P01 schema foundation 已在CR-OUT-001下经 hosted PG lifecycle 验证，migration head为`20261102_0220`。|
|冻结API|API-03 的`OUTPUT_REQUEST_CREATE`为POST project-scoped路径，控制标记 S/L/C/I/A，返回202 RequestRef + JobRef；固定不可变源版本与Context，不能用动态current/latest；失败或不完整授权时失败关闭。P02不挂HTTP，CSRF与HTTP错误映射留后续WBS。|
|冻结模型|DM-04要求同Project归属、requested_by、固定模板/策略/插件操作/source refs、不可变context指纹、request/job/trace refs和幂等身份；Output+Plugin链路固定为 Request+Context → Job+Outbox+Audit。重生成必须创建新generation并保留旧历史。|
|现存事务模式|Platform `SqlAlchemyUnitOfWork` 为单次显式提交；Project Create与Document Parse队列展示业务写、Audit、Idempotency receipts和Job/Outbox共用调用方事务；Jobs Port不得自行开启/提交事务。|
|安全接线|使用现有 Project Session/License/项目权限边界及Audit/receipt模式；鉴权和License检查必须先于幂等回放。拒绝未授权、跨Project、动态版本及空/非固定快照；不记录密钥/正文。|
|现存缺口|P01为了安全给两张新表加了永久write拒绝trigger。本Owner必须通过下一个增量migration移除仅INSERT/UPDATE/DELETE拒绝trigger并允许服务写入，同时保留NO-TRUNCATE与所有数据约束。Downgrade需可重建写关闭trigger而不删除历史数据。此行为是CR-OUT-001明确预留的Owner后续范围。|
|事务与幂等|使用 `IdempotencyScope(actor_id, project_id, V1_OUTPUT_REQUEST_CREATE, key)` 与规范化payload fingerprint；receipt只保存request引用，重放时读取原request并返回固定JobRef，不能越权返回其他Project数据。相同Project/type/input/template/policy应复用既有generation；只有显式Regenerate Owner可增加generation。|
|Job边界|实现Jobs所有的最小`OutputJobQueue` Port/SQL adapter，在调用方事务写`owner_module=output` Job和最小`OUTPUT_REQUESTED` Outbox（只含引用/摘要，不含Context正文）；不实现Worker、Plugin消费者或业务生成。|
|来源解析|请求只接受trusted application输入；以注入的source/template/policy/context resolver验证固定来源、同Project、当前授权与最小快照。P02可用合成resolver完成内部PG验收；生产resolver接线和HTTP入口留后续单项，不把调用端任意JSON视作已授权证据。|
|变化与迁移|仅增加Owner写入、Jobs enqueue Port及用于启用Owner写路径的`20261103_0221`可逆迁移；不改变冻结API/DM语义、角色、Scope或模块化单体，不改写Gate2提交`64cdf09`。若实施需要放宽数据模型/API语义，先另立CR。|
|回滚|`0221` downgrade重新启用写拒绝trigger，保留请求/快照/Job历史；代码回滚后新表重新封闭。不得执行`0220` downgrade删除历史。|
|验收|定向Owner/Job Port单测；PostgreSQL 18并发同Key单写与固定重放、不同载荷同Key冲突、不同Key同generation收敛、授权失败无副作用、Audit/Job失败全事务回滚、合法显式新generation；migration空库及当前head升/降/重升/有数据验证；后端全量、Secret检查及集成云端构建链。|

## 风险与决策

- **事务边界**：Output、Job、Outbox、Audit与receipt任一失败都必须回滚，不能产生孤立Request或裸Job。
- **重放安全**：Project Session/License/权限始终重新校验；不能因为已有receipt跳过授权。
- **Context最小化**：只保存固定版本引用、排序、必要定位和策略参数，不保存客户正文、Secret、绝对路径或整份ORM对象。
- **生成未接线**：本项只入队；不会调用外部AI、插件或生成文件。没有Artifact也不得把Request写成成功。

## 验收边界与下一项

只有托管 PostgreSQL与完整回归证据通过才标`PASS_SCOPE_LIMITED`。本项不代表HTTP/UI、真实来源解析、Plugin、Artifact、Windows 11/Gate 3/Pilot/Release通过。下一项在此验收后做来源/模板策略解析或HTTP创建入口的单问题前置检查，以STATUS为准。
