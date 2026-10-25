# P03-A07-P01 Jobs caller-UOW 续租

日期：2026-09-26；状态：PASS（Jobs内部技术Port，非受权Worker/调度器）。

编码前检查：Phase2 / AUD-03-A06-A04-P03-A07-P01；输入现有JobLeaseRepository/JobLeaseCheckpoint与原授权锁序；前置实际发布/恢复/内容/Windows只读组合PASS。涉及Jobs Application公开Port，既有Job/Lease/Attempt；无Schema/API/角色/依赖改变。

证据：通用JobLeaseService.heartbeat自有UOW并commit，无法加入Audit Owner原Root/pair/当前授权的同一短事务；现有JobLeaseCheckpoint故意仅检查。选择独立caller-UOW renewal Port，保持原checkpoint只读；不增大固定超时代替续租，不在长文件I/O事务中持锁。

本项仅证明Jobs实际当前Job/Lease/Attempt技术来源、期限/fence/worker与续租原子性，不证明Audit当前权限或合法Root，后者留P02。调用者先授权/绑定并沿User→Project→Root→Queue→Job锁序，续租结束后及时commit；不得当可复用权限。续租本身不完成Job、不追加业务Audit、不生成结果、不取消/复活终态。

验收：严格UUID/worker/token/int时长1～3600，check_current前后实际完整claim相同；真实PG活跃续期、三事实保持、旧代/错误worker/取消/过期拒绝，caller后置失败全回滚；原checkpoint/lease/发布回归。目标账户/调度线程/实际权限/长任务/三平台/Gate/交付包仍待。

## 验证结果

- Changed/Files：新增Jobs Application `lease_renewal.py`，独立caller-UOW Port和check→heartbeat→check完整claim重核；5新增unit、真实PG验证脚本和本进度/状态/决策/版本说明。原JobLeaseCheckpoint只读行为及通用LeaseService均不改。
- Migration/API/依赖：无，head0042；无HTTP/角色/基线变化，不自commit、不完成/取消/生成业务成果。升级无需数据迁移，撤未装配Port保全部历史。
- Tests：5项unit实际执行，严格坐标/时长含bool拒绝、调用顺序/no commit、前置stale不renew、后置claim变化/到期和不合约返回拒绝。
- 真实PG18隔离库：双Scope现有实际受理/claim/render来源的两期限一致续期；并发两续租串行且claim不变、没有业务Audit/结果/Attempt变化；未commit和caller后置异常整UOW回滚；错Worker/fence、已成功、CANCEL_REQUESTED、实际2秒到期拒绝无写；真实接管后旧代拒绝/新代续期成功。合成测试取消最终由实际公共Port关闭，未伪造业务成功。
- 回归：原实际发布/双Scope字节/撤权取消到期/四类写后回滚/取消两锁顺序通过；全后端Windows11/Python3.13 968项无失败（2既有符号链接权限跳过）。开发wheel成功578370字节，SHA256 `e940854f5c0d9f2f8c831d22c5f96806706d42189158284f7536a32e21de036b`，非可用安装包。
- Result：本Port PASS，只证明技术续租，不证明Audit当前权限/Root/pair绑定合法或调度存活。Lease不代表业务授权，不能直接用裸坐标为审计任务保活。
- Known Issues/Next：P03-A07-P02 当前Audit授权/原Root与受理pair绑定的短事务心跳；随后实际调度、失败取消恢复/Worker循环和提交/Jobs HTTP。正式账户/三平台/性能/质量/Gate3/UAT与整体可用包仍待；POST保持关闭。
