# P06-P07 有界后台单步

2026-09-27，INTERNAL_PASS，非完整进程/安装包/Gate通过。编码前：Phase2/P06-P07，CR-AUD-004/ADR011，前置领取/执行/耗尽收尾及确认恢复已验。Audit单步内存调度，复用原Jobs Port；无实体/Migration/API/权限/依赖变化。

每次最多一个实际动作，交替优先耗尽收尾/正常领取，当前实例不并行step。stop仅停止新准入，已领取命令仍按真实状态完成/重读；不强杀/自动取消/删文件。执行异常保留已知pending，后续先真实Reader（同Supervisor静止锁）核旧代或前两次到期，才释放本机pending让后续实际重领；不改DB、不宣称成功。其他pending再调用原执行器。无法验证终态/身份/活线程仍报错保留，不盲领其他任务。

验收：Unit停止/互斥/公平优先/异常pending及真实facts绑定；PG双Scope真实PENDING至发布、撤权安全失败和停止不领取；原链路回归。风险：坏源/无法核验终态仍可阻该实例，隔离/运营诊断后续补；本项不是进程loop/CLI/服务安装/完整包，撤内部装配保历史回滚。

Changed/Files：Audit worker_step有界实例内互斥/交替优先/stop Event/已知pending保留；6项unit、独立validation，STATUS/CHANGELOG/CR-AUD-004/DEC242留追溯。Migration/API/依赖无变，0042保留，无升级/生产操作。

Tests/Result：Windows11/Python3.13后端1090无失败，2既有权限跳过；真实bounded PG/Vault双Scope从实际PENDING、专属准入、同真实周期heartbeat到真实发布；空扫描/stop六表无写不领取、真实User停用安全FAILED无正文旁路，原发布夹具回归通过。调度交替/实例互斥/timeout保pending/stop后先续原命令/静止Reader拒绝活线程/错facts绑定/前两次到期仅释放本机pending为Unit证据，不冒充真实多Worker或线程timeout综合验收。

Build：开发wheel 624652 bytes，SHA256 `23e991313149a0c999b900d4e37c7ddffa3301be5d7703410f610026a175cc15`，非可安装完整产品。

KnownIssues/Next：坏源/无法核验终态可阻实例；交替只保证此实例尝试优先顺序，不证明全局公平，未知跨进程恢复/服务loop/CLI/HTTP/正式信任/质量/其他平台/完整Scope/Gate未完成。下一P06-P08有界主循环与可中断等待/排空停止，不强杀线程。
