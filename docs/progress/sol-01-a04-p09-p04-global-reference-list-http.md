# SOL-01-A04-P09-P04：GLOBAL Reference List 独立游标/HTTP/Windows

日期：2026-10-09。范围：冻结 `SOL_REFERENCE_LIST` 的 GLOBAL 路径增量；不改 PROJECT 读取、Schema、业务权限或来源资格。

编码前核查：Phase 2；前置 P09-P01/P02/P03 均已通过。输入为冻结 API-04、独立 GLOBAL ReadService/Repository 与当前 Admin/License Session；Reference 根表和当前版本表不变。验收覆盖安全摘要、有界分页、专用家族/密钥/Session/页大小绑定、非 Admin/License 拒绝、Windows 缺钥拒启动和隔离 PG。正式目标账户密钥尚未供给，只能标合成验证通过。

实现：GLOBAL List 用独立游标签名家族和 `global-reference-list-cursor-v1` Vault KeyRef；Windows 显式 read/write 模式可注入，默认应用 404。GET 只返回安全摘要，POST 在只读模式 404；写模式既有 GLOBAL Create 优先。不存在客户正文或确认现时有效断言。

验证：合同测试双页/跨 Session/页大小/PROJECT 家族/篡改/查询负例；Windows 临时 Vault 新钥、丢失、备份恢复及缺钥启动拒绝；隔离 PostgreSQL 18.6/ASGI/真实 Session 对一个合成 GLOBAL 对象做列表和 `after` 空页、撤回后历史读取及拒绝路径。PG 夹具仅单对象，真实数据库双页未验；全量后端结果见 STATUS。`P09-P05` 浏览器和正式用户确认仍待。

兼容/迁移/回滚：无 Breaking Change、Schema/依赖/数据迁移。关闭可选列表路由恢复 404，不删除 Reference/确认/Audit。正式 License/账户、Server 2025、20 并发、Gate 3/UAT/发行未通过；Debian 13 依用户指令跳过。

TraceLink：API-04 → P09-P01 → P09-P02/P03 → 本 P09-P04 → P09-P05 前端。
