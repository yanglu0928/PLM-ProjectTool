# P03-A07-P03 有界周期心跳协调

日期：2026-09-26；状态：PASS（内部有界周期协调，非生产Worker主循环）。

编码前检查：Phase2/P03-A07-P03；前置P02真实当前授权心跳PASS，输入原User-first短UOW/原根与Lease绑定。单一问题为内部周期协调器，涉及Audit Application线程生命周期，无Schema/API/角色/依赖/Scope变更，未装配Worker主入口。

策略：显式Supervisor每实例最多1～20活动线程，默认4；同Job不允许并行心跳；立即首心跳后Event有界周期等待，lease时长3～3600秒、间隔0.01秒到时长1/3。调用既有受权短事务服务，文件I/O在主工作线程、无跨线程共享SQLAlchemy Session。停止仅发Event并有界join；真实线程结束前不能释放槽或复用Job，超时不是已停止。故障存安全code、停止续租并由check/stop传播，STALE_LEASE不能解释成成功。

发布竞争：心跳和发布串行竞争实际Job/权限锁；发布先完成可能使下一心跳STALE，协调器必须传播而不是覆写结果；上层须按P04实际成功源恢复核验判断，不凭心跳异常宣告成功或改回失败。无需新CR：内部调度实现，不变冻结技术/权限/API。

验收：真线程容量/重复Job/启动失败收尾、周期/停止不再调用、停止超时仍占槽、错误安全化与claim绑定；真实PG短租约+人为慢实际文件写跨原期限仍完成、撤权取消/失效停止、发布先成功后心跳STALE不会更改不可变成功源。模拟慢磁盘非性能证明，正式主循环/三平台/质量/Gate/交付包待。

## 实施与验证

- Changed/Files：新增Audit `heartbeat_coordinator.py`，Supervisor进程内有界Job→handle登记、即时首心跳/周期Event、非daemon线程、actual is_alive容量判定、stop有界join、check/wait_ready/stop安全故障传播；5新unit、真实PG验证脚本及配套决策/状态/版本。
- Migration/API/升级：无，head0042；无角色/新依赖/HTTP/生产装配变化；撤未装配协调器保历史无需数据迁移。每实例默认4、可1～20，不是跨进程全局限额，也不强制杀死Python/SQL线程。
- Unit：5项实际执行，真实即时/周期调用与stop后不再调用，重复Job和容量拒绝、活跃调用stop timeout仍占槽、结束后复用；底层私有异常安全化、STALE_LEASE传播不是成功；strict时长/间隔/claim绑定、线程start故障收尾。
- 实际PG18/临时文件：两Scope260条完整原发布，周期受权短UOW把3秒租约维持跨原到期时点；实际文件提升后的返回人为延迟4秒，主文件线程active UOW为0，期间新线程每次独立授权/续租，最后真正AVAILABLE/Result/Job原子成功。成功后再心跳STALE，七表快照无写；真实User撤权和Job取消后周期停止并传播错误，线程实际结束，撤权停后无续租写。
- 原真实发布/双Scope/故障回滚/取消锁竞争回归通过。Windows11/Python3.13全后端978项无失败，2既有符号链接权限跳过；开发wheel成功581005字节，SHA256 `2b61166444d4f3659413fdc6ae91566139558ff69b3b1f3abfa6fc85c8ded8ba`。不是可用安装包。
- Result：内部周期协调PASS。人为延迟是真实物理发布周边的故障模拟，不是实际磁盘慢/性能验收；许可证合成、系统材料唯一临时Vault，正式账户未验。最终成功必须由Owner实际源判断，不能根据协调器错误或线程退出猜成功。
- Known Issues：被数据库锁/网络长阻塞的同步调用不能由join强制终止；stop timeout明确失败并保容量，线程非daemon，正式Worker停机必须设置可验证DB超时/失败策略。没有进程服务主循环、claim分派、全局停机或业务失败/取消恢复Owner，不宣称运行包可用。
- Next：P03-A07-P04 Worker单次协调生命周期/DB有界等待前置核查，后续实际claim→capture/render/publish或恢复、失败取消收尾/主循环，再提交Jobs HTTP；正式三平台/质量/Gate3/UAT/交付Scope保持。
