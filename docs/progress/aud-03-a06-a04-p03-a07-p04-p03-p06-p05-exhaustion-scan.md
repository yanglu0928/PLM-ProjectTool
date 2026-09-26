# P06-P05 到期耗尽只读发现

2026-09-27，INTERNAL_PASS，非完整模块/安装包/Gate PASS。编码前：Phase2/P06-P05；输入CR-AUD-004/ADR011，前置P06-P04同事务终态/来源核验已验。涉及Jobs只读候选Port/Repo与Audit受控单候选收尾；无实体/Migration/API/权限/依赖变化。

目标：固定audit/AUDIT_EXPORT，RUNNING/max3/count3/未完成Job、当前一致ACTIVE Lease/未完成第三Attempt、真实DB clock已过期，只读取最早到期一个候选。明确不是授权/全队列为空证明；候选可能已变，收尾必须原Root/pair/Worker-fence/到期/identity/静止锁全部重验。不得从hint直接改状态或读取正文。

验收：Unit无写/无候选/类型绑定/identity/真正确认恢复；真实PG双Scope六表只读、同源受控收尾和commit后确认恢复，原执行器回归。竞争/损坏源不猜成功或跳过，公平调度/隔离/循环后续任务，不宣称已交付。

风险/回滚：该只读扫描不隔离坏Root，不强杀其他进程。撤未公开sweep装配保失败/Audit历史；没有生产迁移或自动删除。

Changed/Files：Jobs audit_export_exhaustion_scan候选Port/新Repo；Audit sweep_exhausted_export；6项unit/独立validation/verify.py。P04验证夹具新增可选装饰入口，默认路径不变。STATUS/CHANGELOG/CR-AUD-004/DEC240追溯；Migration/API无变化，Schema仍0042，无升级/生产操作。

Tests/Result：1081项后端无失败，2既有Windows权限跳过。真实独立临时PG/Vault两Scope：到期第三代实际一致Worker-fence/原export候选、六表扫描无写、调用原Owner安全失败、真正commit后确认故障核源恢复，完成后无候选/无写；复用P04实际三代到期/前代活租约错Worker拒绝、Audit/state故障回滚、真实User停用/合成License正文拒绝而安全失败、旧字节保留，及夹具原发布回归。空扫描只证明本次查询无候选，不代表队列整体健康。未运行公平性/多Worker并发sweep/实际网络断线，不能虚报。

Build：开发wheel 622601 bytes，SHA256 `e33cec8608606f0d38b837d1ad950a2b1f55431793b8fd3aab3fdbc24af9750a`；非可安装完整产品包。KnownIssues：坏源可能阻最早候选、需后续隔离与公平调度；claim确认恢复/loop/CLI/HTTP/正式信任/质量/三平台/Gate未完成。Next P06-P06领取提交确认丢失核源恢复。
