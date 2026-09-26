# JOB-02-A02：Audit Owner的JobId取消解析

2026-09-27 / Phase2，实施前检查。前置JOB-02-A01及0043、原Audit事务/授权/完整pair与不可变接受记录满足；输入冻结API-03 Job取消和CR-JOB-003。单问题：通过可信Audit Owner Application Port以JobId解析原Export，不让客户端提供/猜export_id；复用同一个UOW授权/锁/版本/幂等/审计与重放。

涉及Audit Application DTO/原取消Service/owned Repository方法，不新增Job表SQL、Schema/Migration/API/角色/依赖。新增RequestAuditJobCancel强制expected_version（None/bool拒绝）；仅内部Audit Owner入口。先Audit immutable acceptance无锁查Root，再当前原License/Session/CSRF/Project creator-or-PM/Admin授权，之后Root锁+原acceptance真实Audit+完整Job/pair验证，accepted.job_id必须等请求JobId，首次及重放都检查。请求指纹仍从实际Root生成，原export_id入口历史不改。

风险：预查不是授权；不得由解析成功返回正文/权限或当可公开API。实际Jobs Queue会再查owner/type/scope/actor/payload/ref，禁止未知Owner回退或伪造接受记录。无业务读取权限扩大，IM可读任务但不因读取权取得他人取消权。未来generic Job路由需显式Owner注册并先当前Session验证；公开完整JobView/首次响应快照另验，不能拼新旧混合版本。

选择最小复用而非新取消子系统/客户端export_id映射。可逆内部实施符合持续授权，DEC-266记录；无需DDL或冻结Breaking变更。Rollback撤新Owner入口保原export命令与历史Job/Audit/receipt。不生产操作。

结果INTERNAL_PASS：RequestAuditJobCancel强制显式版本，原Service同UOW解析Root并验证受理JobId；Repo只查Audit-owned表，无Job私有SQL。5新增单位行为，Windows11/Python3.13.15后端1165无失败（2既有权限跳过）。真实PG双Scope PENDING取消v2、RUNNING请求→实际Worker确认v3；原export入口同Key同指纹重放原结果，确认后保原CANCEL_REQUESTED且十表无写。缺Job/ExportId当Job/错Scope/跨Project/IM他人/Admin项目/CSRF/过期版本/改指纹/License、停用用户重放均拒绝无写；实际Audit后故障整事务回滚。原A01版本/发布空与260行、实际取消-发布锁竞争回归通过。本轮无测试失败；进度追加首次定位文本不匹配，重读后修正文档补丁，无代码影响。

开发wheel 645648 bytes，SHA256 `a83c2e7713e1df4d6886614a3cfd1b71a8968370c62c99b0e427b513f9725eb9`，不是完整安装包。无本轮Migration/API/依赖/升级，需0043；正向License合成、SystemActor实际临时Vault，不代表正式账户/三平台/性能/Gate/包PASS。

合同再核查：API-03只冻结JOB_PROJECT_CANCEL，未登记JOB_ADMIN_CANCEL；内部DEPLOYMENT不等新增HTTP许可。取消结果为200取消/终态，完整JobView是GET合同，不为取消额外构造混合快照。但API-01更新需强ETag且同Key原结果，原Audit收据没有首次lock_version，不能拼当前version与旧state；Next JOB-02-A03先CR/最小取消结果版本持久快照验收，再项目取消HTTP，保其他Owner/列表/重试完整Scope。

验收：命令类型/强版本、相同UOW Root及Job绑定、缺失/错Job/错Scope拒绝，无取消写；真实PG双Scope JobId PENDING/RUNNING/原重放/版本冲突/当前CSRF-License/跨项目与IM他人取消拒绝、故障全回滚；与既有export入口同Key去重，原版本/Worker取消/发布回归、全后端。结果待追加。Next：公开Job取消响应持久快照前置与If-Match HTTP，不删其他Owner/列表/重试。
