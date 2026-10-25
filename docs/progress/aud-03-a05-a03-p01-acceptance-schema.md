# AUD-03-A05-A03-P01：不可变首次受理结果Schema

日期2026-09-26；Phase2；0.1.0.dev0；结果ISOLATED_ACCEPTANCE_SCHEMA_PASS。完整提交/真实Job关联/权限/HTTP尚未验收。

## 编码前检查 / Changed / Files

A03核查发现0037 Root与通用receipt没有固定首次Job/Event ID，现存可变Job lookup不足以独立证明原响应。任务只补不可变首次响应存储；实施前修订CR-AUD-001，保留0001～0037及冻结64cdf09，不静默改旧Root或假定“现存任务=首次任务”。输入冻结API-02/API-03、A04意图和A05-A01/A02，前置满足；模块Audit，新增auxiliary acceptance，不新增公开Root/API/角色/Scope/依赖或授予权限。

新增0038及export_orm AcceptanceRow、3项unit与隔离verify.py；更新head/metadata测试，P02历史down断言改成真实ScriptDirectory head，覆盖多步DDL失败整体回滚后版本保持不变。表export_id为PK/FK指向own Root，首次Job/Event/请求Audit ID分别唯一，Audit事件为own FK；accepted_at固定。Job/Event只opaque Ref，没有跨模块私有表读取或SQL写，真实存在/绑定必须由A02公开Port在后续主命令验证。

插入先锁Root FOR UPDATE，核验原Trace/USER Actor/Scope/Project/purpose、请求Audit action/outcome、jobs/JOB-01真实typed目标对应job_id、无target version、before NULL/after PENDING，事件及受理时点不早于请求，源事件不得晚于受理。不得把Export假装AuditEvent/AUD-01。UPDATE/DELETE/TRUNCATE全部拒绝，首次引用不随Job状态/后续请求变更。旧Root不猜测回填Job ID，缺受理历史时后续重放必须拒绝。

## Migration / Tests / Result / API / Compatibility

0038新增一表/guard及继承0037不可变拒绝函数。down先ACCESS EXCLUSIVE锁受理表，任何历史拒绝、不销毁结果；离线down关闭。生产升级需备份/维护窗口，本轮只独立UUID库，未运行生产migration。

Win11真实PostgreSQL空库up/down/re-up、旧Root/Audit有数据down/up保持原行且无猜测回填、ORM parity无diff；合法PROJECT/DEPLOYMENT受理，Trace/Actor/Scope/action/outcome/purpose/typed目标/Job ID/version/before/after/时间错配拒绝；零UUID/缺根/旧审计拒绝，Root/Job/Event引用唯一和不可变实测通过；down竞争ROW EXCLUSIVE写锁真实阻塞，含受理历史拒绝且head0038/原行完整。测试Job/Event ID为合成opaque Ref，没有真实Jobs存在/授权或receipt编排证明，不能据Schema放行POST。finally清理独立库，无客户数据。

后端839项无失败，2项既有符号链接环境跳过；新3项unit验证最小字段/owned FK/唯一/离线down/历史守卫。P02 capture Schema、P03实际single-statement/晚提交/回填/故障/重放、A05-A01实时提交授权（License合成）、A02 Job pair并发/回滚/绑定/终态回归PASS。开发wheel PASS，SHA-256：`3246068169c06bbadeb7961d24d5db51bd28c66e1379605c5a3b9785bb3a6c11`，非正式安装包。

无公开API/角色/依赖变化。0038有受理历史禁止down，旧无结果意图保留不伪造；不把迁移授权等同生产操作授权。Server2025未验，Debian13暂缓但正式目标保留；质量/实际业务Owner/正式信任材料/性能/Gate3/UAT/完整可用包未完成。

## Next

AUD-03-A05-A03-P02：Root create/read/acceptance写读与完整实际授权→receipt→Root→Job Queue→请求Audit→acceptance→receipt完成同UOW，重放先当前权限/Spec再原acceptance及Job公开Port精确原ID核对，故障/并发/真实死锁有限重试验收。尚无完整受理命令或导出POST。
