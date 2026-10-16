# JOB-02-A03：取消首次版本快照

2026-09-27 / Phase2 / INTERNAL_PASS。编码前CR-JOB-004与DEC-267登记；输入冻结API-01/03、0043及A01/A02原当前授权/同事务取消/收据。仅解决原结果版本，不构造额外完整GET JobView。

Changed/Files：0044与Audit ORM增加aud_export_cancel_versions(event PK/FK,非负bigint lock_version)。INSERT真实受理USER取消事件来源约束、UPDATE/DELETE/TRUNCATE拒绝；down先ACCESS EXCLUSIVE锁，含快照拒绝，保护历史。Audit取消Receipt末尾可选version，原export入口/旧收据保None，新JobId首次请求同原UOW读取Jobs owned实际锁版本并记录，来源读取始终由原Audit事件核actor/scope/project/Job/state/changed，重放不拼当前版本。Schema/模型增量另记，旧迁移/冻结提交不改。

Tests：Windows11/Python3.13.15/隔离PostgreSQL18，全后端1167项无失败（2既有账户权限环境跳过）。2新增Schema/DTO单位行为，原Job命令单位增加实际首次记录断言。validation/job-02-a03-cancel-snapshot/verify.py实际空库up/down0043/up；真实旧发布/取消历史十表降至0043再升级0044不变，新表空不猜旧值，ORM列/类型/null parity；两Scope即时CANCELLED首次v2、RUNNING首次请求CANCEL_REQUESTEDv2，同Key并发两次只一快照且结果相同，真实Worker确认当前v3后重放仍原state/v2；旧export入口收据None保留、JobId重放不补写。

实际坏来源/负版本/重复/UPDATE/DELETE/TRUNCATE拒绝十一表不变，含快照down拒绝且Alembic head0044/旧历史不变；实际快照insert后异常使Job/Lease/Attempt/Audit/receipt/快照等十一表全回滚，过期新Key/同Key改版本/License拒绝无写。原A02 Owner解析/角色隔离/CSRF/停用后重放与原publication双Scope真实文件260行/取消-发布锁竞争回归通过。

失败与修复：首次Schema parity脚本错误访问DatabaseRuntime.engine（无该公开属性），改为UOW session.connection真实连接；首次全量metadata登记断言尚未包含新owned表，扩展精确表集合而非删用例，重跑均通过。未改实际验收标准。

开发wheel647438 bytes，SHA256 `b2df4b29c5c96d77514efa4704c29c67f52e4d54d72ce182ef5c44f5ebd69da5`。此为后端开发wheel，不是可用完整安装包。Migration：0044本轮仅独立UUID库；升级生产需备份/维护停写，新历史存在不可降级丢失。Rollback停新入口回旧代码时保0044与历史；正式恢复人工执行，不能自动删除快照绕过。

API/Architecture：无新HTTP/依赖/角色/License机制/技术栈；冻结项目取消路径待下一项，Admin取消未冻结不自动增加。旧收据None未来HTTP必须失败关闭而不是猜ETag；普通内部历史仍兼容。Known Issues：合成License与实际临时Vault不是正式目标账户材料，三平台/性能/完整Scope/安装/Gate仍未完成。Next JOB-02-A04：项目 :cancel 可选HTTP，强If-Match/CSRF/持久首次结果/显式Audit Owner，仅关闭默认/未知Owner，不新增Admin取消。
