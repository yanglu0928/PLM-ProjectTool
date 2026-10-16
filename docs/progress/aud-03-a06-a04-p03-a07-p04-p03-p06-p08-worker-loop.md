# P06-P08 主循环与可中断等待

2026-09-27，INTERNAL_PASS，非正式进程/发行/Gate通过；编码前Phase2/P06-P08，前置P07单步已验，CR-AUD-004/ADR011。只编排原Audit单步，无DB/API/实体/依赖/权限变化。

run允许显式步数上限或持续运行；实例互斥，空闲Event.wait可被stop唤醒。stop传递单步停止新准入，继续原已知pending排空；只有原单步实际返回STOPPED才报告STOPPED，达到上限只报LIMIT，不假称已安全停机。异常退出不自旋/盲重试，保原Step pending供同实例后续核验；不强杀线程、不处理进程信号/安装服务/自动重启。

计数只存聚合数，不缓存业务输出/客户正文。验收：Unit真实单步组合的有界run/停止唤醒/异常保留/互斥/非法参数；真实PG双Scope单步发布链经run运行，原验证回归。风险：阻塞外部I/O仍不能强杀，未知跨进程命令恢复/坏源隔离/CLI后续验。撤内部Loop装配保历史回滚，非完整交付/Gate通过。

Changed/Files：Audit worker_loop、5新unit、独立validation；P07夹具新增可选Step装饰入口（默认不变），STATUS/CHANGELOG/CR/DEC243追溯。Migration/API/依赖无变，0042保留，无数据升级/生产操作。

Tests/Result：Windows11/Python3.13后端1095项无失败，2既有权限跳过；真实独立bounded PG/Vault两Scope从PENDING实际领取、周期heartbeat到真实发布经原Loop run(max_steps=1)，当前User停用安全FAILED、空/stop六表不写，LIMIT与STOPPED真实区分；原发布夹具回归通过。Unit真实Event.wait被另一线程唤醒、并行run拒绝、异常保原pending和同实例stop排空/参数边界通过。不把有界进程内loop证明当CLI/服务/进程信号或多Worker公平证明。

Build：开发wheel 625807 bytes，SHA256 `cce123f44ef21383af88c0f9a2ffd1bee1102635db1252f920f867851a9360be`；非完整产品安装包。

KnownIssues/Next：阻塞I/O不能强杀，坏源/无法核验终态可阻实例；未知跨进程恢复/运行组合根/CLI信号/服务/公平隔离/HTTP/正式信任/质量/其他平台/Gate/完整Scope包未完成。下一P06-P09组合根与启动前置核查。
