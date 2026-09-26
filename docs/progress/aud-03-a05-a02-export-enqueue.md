# AUD-03-A05-A02：Jobs owned审计导出最小引用队列

日期2026-09-26；Phase2；0.1.0.dev0；结果TRUSTED_QUEUE_PASS，未装配公开入口。不是真实Audit根/授权/完整提交/Worker/HTTP/发行PASS。

## 编码前检查 / Changed / Files

本项只解决Jobs跨Owner专用enqueue前置。输入冻结DM-04/API-03、0036 DEPLOYMENT修正、现有Job/Outbox/lease、A03Spec/A04存储/A05-A01实际提交权限；前置满足。涉及Jobs两owned表及最小DTO，不改其他模块。DEC-20260926-195实施前明确域分隔事务锁、不可换绑定、原Trace/终态重放规则。新增application/audit_export_enqueue.py、infrastructure/audit_export_enqueue_repository.py、5项unit及独立验证脚本。无Schema/API/角色/依赖变化。

请求固定Export UUID/原Actor/PROJECT或DEPLOYMENT/Project/原Trace/V1政策；无任意payload/Session/CSRF/Secret/路径/事件正文。Job payload仅export_id+policy_version，Outbox另含job_id；type为AUDIT_EXPORT/AUDIT_EXPORT_REQUESTED、aggregate_version=1，Job3次/Outbox5次技术重试。新Job/event使用PostgreSQL18 uuidv7。Queue不能检查Audit内部表，可信Caller必须先真实授权/根绑定，DTO不证明来源存在或权限。

固定READ COMMITTED，按ExportRef域分隔SHA-256得到signed64 advisory xact lock，同Export跨Scope串行，碰撞仅额外等待，实际完整绑定和数据库唯一性独立核对。Job→Outbox owned行锁，两个记录都完整才返回Ref；同Export换Scope/Project/Actor/原Trace/政策、异payload/aggregate或缺一行均拒绝，不修复半任务/不复活终态。查找不创建业务行，enqueue不自建UOW/commit/rollback/鉴权/发布。首次Trace来自原持久Export，API重放外层新trace不能改写原任务。

## Tests / Result / Migration / API / Compatibility

Windows11/Python3.13后端836项无失败，2项既有符号链接环境跳过。5项unit覆盖固定最小字段/冻结、完整Scope/UUID/政策、腐损再验先拒绝、结果/lookup None及signed域锁键稳定，mock不冒充真实权限。

独立UUID PostgreSQL实测PROJECT/DEPLOYMENT各自产生一组最小payload且原Trace/Actor精确，uuidv7、lookup不建业务行、重复返回相同Ref；终态CANCELLED/Outbox DEAD重放原始整行完全不变。错Actor/Trace/跨Scope绑定拒绝；同一活跃第二调用者在事务锁真实等待，首次提交后返回原pair，数据库各仅1行。调用方不commit两表回滚；Outbox写故障整UOW回滚，重试重新正确创建；只删除own synthetic Job或Outbox制造缺边时明确拒绝不补写，篡改payload拒绝。Audit根表始终0行，清楚表明测试只用可信合成ExportRef，不是根存在/实际业务权限证据。finally清理独立库，无客户资料/生产操作。

既有部署Job/Outbox Schema与Document Parse限制、真实Job两Worker/heartbeat/takeover/fencing/发布回滚/限次重试/attempt历史、Outbox旧数据升降级/ORM parity/并发投递/消费回滚去重回归PASS。旧Review/Workflow computed default产生既有Alembic告警，实际parity仍无diff，不以告警当新验收失败或忽略实际错误。开发wheel PASS，SHA-256：`fdcb3ccaf261cb35da0b3cf00d46fcacfc9360442680f0d0f6d72107746eece0`，非正式安装包。

无Migration/API/角色/Scope/依赖变化，升级无数据动作；可撤未装配Port，不删除历史Job/Outbox。未运行Audit授权→receipt→根→Queue→请求Audit完整原子/死锁恢复、Worker当前权限/Lease/取消/文件/HTTP/性能验证。普通导出POST仍关闭，Server2025未验、Debian13暂缓且目标保留。实际Owner/质量失败/正式信任材料/Gate3/UAT/完整可用包仍待。

## Next

AUD-03-A05-A03：实际受权创建、不可变首次Export/Job响应、receipt/请求Audit与enqueue全UOW原子；重放用原Root固定Actor/Scope/Trace/政策核验原Ref且当前权限重新检查。核对真实锁序/故障全回滚及并发重放，之后Worker/交付。不跨模块读写Job内部表，不把单独Queue默认公开。
