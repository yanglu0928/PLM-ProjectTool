# AUD-03-A06-A02-P01：事务内当前租约检查

日期2026-09-26；版本0.1.0.dev0；Phase2；结果LEASE_CHECKPOINT_INTERNAL_PASS。不代表取消命令或完整Worker验收。

## 编码前检查 / Changed / Files

依据DEC-20260926-198先记录后实施。输入既有DM-04/API-03租约与A06-A01当前权限；前置满足。只解决capture/render所需事务内只检查入口。新增jobs/application/lease_checkpoint.py公共Port/服务、owned lease_repository.check_current、4项unit和独立真实数据库验证，不跨模块访问表。

输入精确nonzero UUID、正int64 fencing token、规范worker；bool不冒充token。owned实现沿Job→Lease→Attempt锁序读取当前RUNNING、同token/worker、ACTIVE lease、未完成attempt，数据库clock_timestamp核验未到期，并检查Job/Lease到期时点与attempt计数一致。返回既有ClaimedJob只作当前绑定元数据，不是权限或跨事务通行证。没有heartbeat、finish、UOW创建或commit；caller短事务结束才释放锁。长文件I/O不持锁，发布须再次检查租约及当前权限。

所有非RUNNING状态（含CANCEL_REQUESTED/CANCELLED）均失败关闭，不复活任务或自动修复腐损。但本项取消状态由测试设置，只证明拒绝，真实受权取消/协作确认/审计/恢复仍待P02，不用枚举代替行为。

## Tests / Result

Win11/Python3.13/PostgreSQL18独立UUID库：实际Job claim后公共checkpoint返回原generation且Job/Lease/Attempt/Audit表不变；错误worker/token/未知Job拒绝；三事实锁在入口返回后竞争连接真实lock_timeout，caller退出后可取；caller异常回滚不改变数据；合成取消/终态/等待状态拒绝，错attempt编号/错期限/已完成attempt拒绝；真实heartbeat到期、实际第二Worker takeover升token/attempt、旧Worker拒绝，真实finish后再次checkpoint拒绝，不续租/完成/修复。Root/Export payload为合成owner坐标，不冒充已受理Export或业务权限。

857项后端无失败（2项既有Windows符号链接权限跳过），4项新增unit覆盖输入、精确返回绑定、caller事务不commit、错误/无默认依赖。既有真实双Worker租约/heartbeat/接管/发布回滚/有界重试/完成历史回归通过。开发wheel通过，SHA-256 `96ee17b873fc4fdbaa5b310a1ad9a57040ffef0d34aa756d4b87f745e1418bad`，不是正式可用安装包。隔离库finally清理，无生产操作或客户数据。

## Migration / API / Compatibility / Known Issues / Next

无Migration/API/角色/依赖变化，head0038不变，升级无新动作；回滚可撤未装配入口，不删除历史。Server2025未验，Debian13暂缓但正式目标保留。安全事实锁不能阻止时间本身流逝，发布前必须重验，不能把一次成功当永久许可。Lease不是业务授权，A01及持久Root/acceptance/实际Job Scope/Actor绑定仍需在后续Owner编排接入。

下一项AUD-03-A06-A02-P02：Jobs owned受控取消与协作确认/到期恢复公共事务Port，随后Audit受权取消及Worker capture/发布编排。未开放导出POST，Artifact、取消完整链、正式信任材料、性能、质量、实际业务Owner、Gate3/UAT及完整程序包仍待；总体Scope不缩减。
