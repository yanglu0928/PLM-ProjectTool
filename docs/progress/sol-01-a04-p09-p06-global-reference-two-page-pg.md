# SOL-01-A04-P09-P06：GLOBAL Reference 真实 PG 双页补证

日期：2026-10-09；结果：`GLOBAL_REFERENCE_TWO_PAGE_PG_PASS`，限定 Windows 11 一次性 PostgreSQL 18.6/合成来源。

编码前检查：Phase 2；前置 P09-P02～P04 的独立 GLOBAL Owner/Repository、签名游标与 HTTP 已通过，P05-P04 浏览器单对象链通过。本任务只补数据库真实双条/双页证据，不改生产程序、权限、Schema 或冻结 API。验收为两条真实 Create Owner 插入、当前版本/确认绑定与 Audit、List 按根 ID 两页、PROJECT 游标隔离及缺 Session/License 异常关闭。跨有效 Session 的游标拒绝由 P09-P04 合同测试覆盖，本轮 PG 未另建第二个有效 Session。

在来源夹具的有效人工确认后，正式 `ReferenceCreateService` 用两个不同原 Key 创建两条 GLOBAL Reference，共用同一合成确认的固定来源；数据库有两条不同根及两个 `SOL_REFERENCE_CREATED` 审计。Windows 显式 List 组合在真实 Session/ASGI/PG 下 `page_size=1` 得第一页游标，第二页精确得到下一根且终止；同密钥的 PROJECT 家族游标、换页大小和篡改令牌均 400；缺 Session 401、异常 Origin 和 License 403。列表不投影确认 ID 或客户正文。首轮回调缺端口参数导致测试脚本失败，补齐共用夹具的可选回调参数后重跑退出0；原来源夹具独立回归退出0。PG/私有临时目录按夹具正常停机清理。

限制：合成确认并非真人客户确认；本轮未使用正式 License/目标账户游标密钥，不代表发行就绪。Server 2025、20 并发、Gate 3/UAT/发行未通过；Debian 13 按用户指令跳过。

兼容/迁移/回滚：仅验证夹具兼容扩展，无生产代码、API、Schema、依赖或数据迁移；删除新脚本/可选参数即可回滚，历史业务数据不受影响。TraceLink：API-04 → P09-P02/P04 → P05-P04 → 本 P09-P06。
