# AUD-03-A06-A04-P03-A04-P01：Jobs caller-UOW完成Port

日期2026-09-26；Phase2；编码前检查PASS；限定Jobs完成Port验收PASS。

- WBS/输入：Gate2原64cdf09、CR-AUD-002/ADR007/010、已有原Queue/租约Checkpoint/LeaseRepository finish；结果Repository已验证并同步b4e1c7e。
- 涉及模块/实体：Jobs own Job/Outbox/Lease/Attempt；外部Export仅原request/refs，不读Audit/Document表。
- API/权限：仅内部Audit专用公共Port，无新HTTP/当前Auth/License替代；trusted caller必须先真实授权/own Root/accepted/plan/capture及真实文件，再调用。
- 实施：原request/ref→Queue advisory→Job/Outbox→Lease/Attempt完整当前检查，精确Job type/Scope/project/trace/payload/token/attempt；同caller-UOW再核当前时点finish、比较返回claim，改变Job SUCCEEDED/Lease RELEASED/Attempt completed，无自开UOW/commit/回调/I/O。
- 锁序：Audit Owner未来User/Project/Root在前，再Queue→Job/Outbox→Lease/Attempt→Document；完成放最后当前授权复核之后，调用后不允许长任务或外部I/O，马上caller提交。不能把已完成结果再当active Lease重放；Owner要单独当前鉴权读首次结果。
- 验收：真实双Scope enqueue/claim→caller完成、后置故障全部回滚、旧ref/Scope/Worker/token/过期/不一致拒绝、真正接管旧Worker拒绝、真并发一个完成、实际cancel与完成两个阻塞锁顺序，终态不复活/不修复缺边；旧Lease/取消/Checkpoint回归及后端全集。
- 风险/回滚：无Schema/API/依赖/升级；原LeaseService.finish仍兼容；本任务合成Export/权限/发布marker，不冒充真实文件/业务结果/发布审计/完整Worker。撤新入口保留原历史。
- 预计文件：Jobs Application completion、unit/真实PG verifier、本进度/决策/CR/STATUS/CHANGELOG。

## Changed / Files / Migration / API

新增AuditExportJobCompletion/公共Port，mandatory原request/refs、exact token/worker与当前Claim验证，原Queue完整绑定/租约一致性后同UOW再actual clock finish，并核对完成返回Claim仍同原generation。无新Repository私有访问或其他模块表引用；复用Jobs owned既有公共持久层实现。无新UOW/commit/回调/文件I/O/修复来源，终态拒绝再完成而非复活；成功重放由Owner真实鉴权后读首次业务结果。

无Schema/API/依赖/升级动作，head0042不变，旧LeaseService.finish保持原行为。Owner必须先持当前User/Project/Root/Queue等锁，最后授权/Lease复核之后调用完成并马上commit；Port不保证或允许完成后长时间外部工作。真实完整文件发布还未接入。

## Tests / Result

- 实际PG18 UUID临时库/Jobs Queue/Outbox→claim→caller-UOW完成，PROJECT/DEPLOYMENT均Job SUCCEEDED、Lease RELEASED、Attempt同完成时点且无error；已成功重复完成STALE_LEASE、不重复变更；成功后实际取消返回原终态无变化。
- 原pair/actor/Scope/Worker/token误绑、Lease与Job expiry不一致、PENDING/FAILED/CANCELLED/缺原Outbox拒绝，全部技术表/own Audit/Document/marker快照不变；没有按坐标猜修复。
- caller真实append Audit/marker→完成→故障全UOW回滚；Port正常返回但caller未commit也完全回滚。真实checkpoint后sleep导致finish时expired仍拒绝，整个marker回滚；真实过期接管旧Worker拒绝、新代可完成。sleep只是受控时间流逝，不伪称性能结果。
- 两真实并发完成只有一次成功；实际cancel-first及complete-first锁等待通过pg_stat_activity观察、提交释放后分别拒绝完成或保留成功；marker只是合成DB发布标记，不是File/Artifact/真实Audit Export发布。
- 926项后端无失败（2既有Windows符号链接权限环境跳过）；新增7项输入/nested/Port依赖/精确绑定/不自commit/变返回拒绝及unknown错误安全/不盲retry。旧Lease真实claim/heartbeat/takeover/rollback/retry、取消/Checkpoint及结果Repository真实回归PASS。
- 开发wheel0.1.0.dev0通过，560783 bytes，SHA256 `16df3ec216a10fb0851712216ac00f2165d033917bada070154a9d70e0d10c11`；不是可用安装包。

## Known Issues / Next

Export根/当前权限/业务结果/物理File/SystemActor absent或合成，未证明真正安全发布；本Port只完成实际Jobs own技术事实，不发布审计成果。下一项P03-A04-P02真实固定源的有界文件渲染与短事务授权/阶段检查，再P03-A04-P03结合Document metadata+own Result+正式形状Audit+Jobs公共完成原子发布，逐项客观验收。正式运行身份/License/密钥、质量Gate3、性能/三平台/完整程序包仍未完成；POST关闭，完整Scope保留。
