# CR-JOB-003：取消版本条件与旧收据兼容

2026-09-27，Phase2 / JOB-02-A01，实施前登记，依据持续授权自主执行。输入冻结64cdf09/API-01/API-03、0043与原Audit取消受权/收据事务。原基线、旧迁移及取消历史保留。

证据：公开Job写合同需要强If-Match，但原内部取消命令没有expected_version；0043数据库触发器递增版本后，SQLAlchemy同事务identity map可能保留旧版本，不能拿缓存或Lease fencing作用户并发版本。

方案比较：无条件公开取消不满足合同；强行改旧命令/指纹会破坏历史重放；新增取消子系统扩大范围。选择原命令末尾增加可选expected_version（严格非负bigint，None仅保留旧内部调用）。显式版本加入原operation的请求指纹，旧未提供版本的指纹不变；同Key改变版本/从旧命令改成版本命令均冲突，不新建命名空间绕过去重。未来公开入口必须提供版本，不能采用None回退。

事务：先原当前License/Session/CSRF/资源/角色授权与完整Root/acceptance/pair锁；读取实际Job lock_version；原收据重放先返回不可变首次响应并再次授权，不能因后续版本变化拒绝合法重试；只有新命令在取消之前比较版本，不等报VERSION_CONFLICT，整个事务回滚含新收据占位。原Worker确认/到期恢复/发布竞争与取消首信息保持。锁定Job查询populate_existing刷新实际数据库列，不能猜加一，PENDING即时取消有两次业务更新。

影响/风险：仅Jobs事实DTO/owned Repo与Audit内部编排，无新Schema/依赖/API/角色/License变更。None不能成为未来HTTP退路；重放仍需当前授权；版本不是访问权。原完整Scope、Gate和发行验收不缩减。

迁移/回滚：运行需已验证0043，不生产迁移；撤新调用与版本逻辑即可回旧内部路径，保留所有Audit/收据/Job历史。不对外开放接口，未来公开If-Match和Owner解析另项验收。

验收：DTO拒绝bool/负数/越界；单元证明版本冲突无取消/Audit/commit、旧指纹保留与新指纹绑定、过期版本合法重放；真实隔离PG双Scope PENDING v0→CANCELLED v2/同事务刷新、RUNNING v1→请求v2→实际Worker确认v3/原首次结果重放、过期版本/异Key异版本冲突无持久写、实际权限/License拒绝、审计失败全回滚；原取消/发布回归与全后端测试。正向License仍为显式合成，不代正式信任源、并发吞吐/三平台/完整包。

结果：JOB-02-A01 INTERNAL_PASS，双Scope实际v0→即时v2/同UOW刷新、v1→请求v2→原Worker确认v3、同Key单次/异Key同版本一成功一冲突、终态只检查、旧指纹兼容/版本冲突十表无写、Audit后故障回滚已验。1160后端无失败/2既有跳过，原请求/确认/到期取消与原发布回归、开发wheel通过；详见docs/progress/job-02-a01-cancel-version.md。整体公开取消/全Owner/正式环境仍IN_PROGRESS，不能宣称完整Jobs/Gate/包通过。
