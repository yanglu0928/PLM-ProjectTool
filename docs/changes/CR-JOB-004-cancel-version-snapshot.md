# CR-JOB-004：取消首次结果版本快照

2026-09-27 / Phase2 JOB-02-A03，实施前登记，依据持续授权自主选择最小方案。冻结64cdf09/API-01强ETag及原结果重放、API-03项目取消合同保留；0043及原取消历史不改。

证据：原不可变Audit取消事件已保存状态/changed/actor/Job绑定，但没有第一次返回的Job.lock_version；Worker确认后当前version变化，拼当前version与旧state违反原结果/ETag语义。不能从更新次数猜版本，不为200取消状态额外持久整个GET JobView。

选择最小owned表aud_export_cancel_versions：audit_event_id为PK/FK，lock_version为非负bigint；Audit事件仍唯一状态/actor/Job/变更事实来源。新增0044、ORM、up/down。INSERT须引用真实已受理Audit Export的USER取消请求/检查事件，固定格式/Scope/project/时间/归属；拒绝UPDATE/DELETE/TRUNCATE，down含任一快照拒绝，不自动丢历史。版本由原UOW Jobs owned锁定read_facts获取，不能由客户端或缓存声明。未给旧事件回填猜版本。

影响：AuditExportCancelReceipt新增可选lock_version末尾默认None，旧内部export入口与旧收据保None；新JobId请求同取消/Audit/receipt事务记录一次实际version，重放只读该首次值。旧JobId收据缺快照仍保历史None，未来HTTP必须拒绝缺版本，不能猜值/补写原结果。未知Owner和管理员HTTP不自动增加，无新增依赖/角色/License机制。

迁移/回滚：仅隔离库验证，生产需人工备份/维护停API Worker后0044；没有新行可离线降至0043，已存在快照则拒绝并保持head及历史，不删除信息绕过。如需回旧代码保0044表/历史，停新入口即可。历史版本/正式生产恢复由人工流程；不宣称热降级/三平台验证。

验收：ORM parity、空库up/down/up、有真实原发布/取消数据升级十表旧数据保持且快照为空；合法记录/坏事件/负版本/重复/修改删除truncate拒绝；含数据down拒绝原数据及版本不变；真实两Scope即时cancel首次v2、运行请求首次v2→Worker实际确认v3后重放仍旧state+v2、当前权限/版本/指纹拒绝、Audit/快照插入后故障全事务回滚；原A01/A02与发布回归、全测试/开发wheel。

状态IMPLEMENTATION_IN_PROGRESS。无生产操作/公开取消Router/完整Jobs/Gate/安装包PASS。

执行结果：JOB-02-A03 INTERNAL_PASS，0044/ORM/空与真实已有数据up/down/up十表保持、来源/不可变/负版本/重复保护、含历史down拒绝head不变通过。双Scope真实首次v2→Worker当前v3后重放原state/v2、并发同Key一快照，旧None不猜回填、实际快照insert后故障十一表回滚通过；1167无失败/2既有跳过，原A02/发布与开发wheel通过。详见docs/progress/job-02-a03-cancel-snapshot.md保首次测试问题/修复。此CR本分项完成，公开HTTP与发行/Gate仍待。
