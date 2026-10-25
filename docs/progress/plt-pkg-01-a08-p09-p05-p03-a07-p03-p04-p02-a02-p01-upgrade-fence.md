# PLT-PKG-01-A08-P09-P05-P03-A07-P03-P04-P02-A02-P01：升级窗口维护锁连续持有

日期：2026-10-01；状态：`ISOLATED_CONTINUOUS_FENCE_PASS / UPGRADE_ENTRY_OPEN`。

编码前检查：Phase 2、Gate 2 已通过；输入为 CR-PKG-004、Platform `MAINTENANCE_LOCK_KEY`、P04-P01 的 `audit()` 与 P04-P02-A01 合成恢复演练。前置扫描和维护锁独立功能均已在 Windows11/隔离PG18验证，但现有 `audit()` 扫描返回时释放会话锁，不能直接用于后续复制/Migration 的连续保护。涉及模块仅离线升级工具的维护锁/扫描生命周期，不改正式 API、ORM、Migration、服务入口或客户数据。实体只读维护状态及 FileObject；权限仍由运维入口和目标账户另行验证。验收为旧 `audit()` 行为不变、新升级窗口能在扫描后继续保持排他锁并重复核维护版本，异常时释放；PG18并发 shared admission/状态切换受阻，窗口退出后可恢复。风险是长期持锁导致维护窗口和数据库连接占用，不能据此证明 OS 旧进程静止；回滚撤新封装恢复旧只读扫描，任何未满足的发行门槛仍阻断升级。

结果：`tools/scan_fileobject_jbig_upgrade.py` 新增 `maintenance_window(engine)` 上下文与 `MaintenanceWindow.scan()/verify()`；一次性 `audit()` 改为该窗口的薄封装，原CLI返回合同不变。扫描在只读 Repeatable Read 事务完成，随后维护排他会话锁仍归窗口持有，`verify()` 在新的短事务中再次比对维护态/版本；退出或调用方异常时释放。隔离PG18双连接复核：扫描后其他连接共享锁获取失败、退出后成功，合成升级步骤抛异常后同样释放；原 CLEAR/JBIG/状态/Hash/忙锁验证仍通过。完整Schema0051合成JBIG阻断、备份/恢复第三轮及Windows11单元6/6回归通过，临时PG正常停止。未执行真实安装/升级或客户数据读取。

已证明的是“升级步骤可在同一DB会话锁窗口内开始”，不是步骤本身已存在或可授权：当前仍缺正式备份工单/可恢复性、SCM与旧进程静止、目标账户及目录ACL、正式CLI和Migration失败恢复。P04-P02-A02总体继续开放，`release_eligible=false`。
