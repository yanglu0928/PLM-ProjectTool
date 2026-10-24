# P04-P03-P04-P04 到期取消恢复

日期：2026-09-26启动，2026-09-27完成；状态：INTERNAL_VALIDATED / REMAINING_LIFECYCLE_PENDING。

编码前检查：Phase2/P04-P03-P04-P04；输入CR-AUD-004/ADR011，前置首USER申请原源、受控SystemActor/静止锁、活代ack已验。涉及Audit恢复Owner与Jobs owned当前代到期恢复Port，Job/Lease/Attempt/Audit，无Schema/API/依赖或权限扩张。

证据与方案：通用recover_expired_cancel只有target，没有fence/Worker参数且已CANCELLED可直接返回，不能用于执行器旧代输入或确认丢失证明。保留该历史技术入口，新增严格当前Job/fence/Worker与一致Lease/Attempt、真实clock_timestamp到期检查的caller-UOW转换。Audit依首申请来源/当前SystemActor/同Supervisor静止锁，最小SYSTEM恢复Audit→identity再验→实际到期恢复最后→commit。未到期/旧代/错Worker/成功/已取消/裸技术来源拒绝，不猜STALE成功。

验收：实际PG双Scope真实短租约过期、未过期/错代/Worker拒绝，首历史/字节保留，Lease EXPIRED/Attempt JOB_CANCELLED/Job CANCELLED与恢复Audit同事务；Audit/状态写后故障与identity失败整回滚。租约期限不是进程强杀或磁盘/network停止证明，不清理文件，确认丢失/执行器/HTTP/正式包仍待。

执行证据：新增4项unit及独立verify.py；真实PostgreSQL18临时库、临时Windows Vault、合成文件两Scope验证全部通过，旧发布fixture回归通过。真实2秒租约未到期拒绝、到期活代ack拒绝、严格恢复成功，Audit/恢复实际写后故障与第二identity丢失六表整回滚；错Worker/fence/root/终态/缺首USER源拒绝。撤User和License业务capture仍拒绝，但安全恢复允许，首申请历史、私有字节、结果不变。没有额外执行新恢复/发布竞争，不扩大原fixture证明。

Changed/Files：Jobs caller-UOW严格当前代恢复Port与owned Repository、Audit恢复Owner、unit/验证脚本/决策/状态/版本记录。Migration/API/依赖均无变化，0042保留，无生产升级。Windows11/Python3.13后端完整测试与wheel证据见STATUS和DEC232；wheel599392字节，SHA256 fe0663bb1ec4c89280887d04105e58e1cd4249cb0219baee86ec246952163cdb。首次hash检查误用包名，构建本身成功，改为实际包名复核上述Hash，不掩盖检查错误。

Rollback：撤未装配恢复Owner/Port，保已写Audit/首次历史/终态/字节，不复活CANCELLED。Next：取消提交确认丢失只读核验，再执行器/主循环/HTTP；正式信任锚/Server2025/质量/Gate/全Scope可用安装包未完成。独立验证仅临时环境，不外发客户数据或秘密。
