# TRC-01-A06-P02-P02：Trace 有界图安全续页游标

日期：2026-10-02；Phase 2；状态：**内部可续页 PASS，公开图 API/正式密钥来源未完成**。输入为冻结 API-02 图查询参数和逐节点授权、P02-P01 有界同事务图；决策 `DEC-20261002-610`。原冻结提交 `64cdf09` 保留。

每页都重新调用当前 Session/License/Project/端点 Owner 受权的有界图服务，不接受前页的授权快照。专用 32 字节 AES-256-GCM 游标在 AAD 中绑定 Session 摘要、目标 Project、固定根、方向、关系、最大深度/节点及页大小；密文包含边序位置、当时可见图摘要和 15 分钟时效。若当前图/权限改变，则返回 `TRACE_CURSOR_STALE`，要求新查询，不静默跳边或继续旧图。页仅投影本页边涉及的已授权节点与根；基础图预算/无权过滤的 `truncated` 在末页仍保留，游标不承诺续出预算外的完整图。

验证：单元新增6项覆盖三页、页内节点、Session/Project/查询/页大小绑定、篡改/换密钥/TTL、图或权限变化、截断/无效输入；隔离 PostgreSQL 18.6 合成两页、第三版本文件 RESTRICTED 后旧游标拒绝、新查询仅返回当前可见边且截断，并回归创建/审计。后端全量 1876 项运行/3 跳过/无失败；开发 wheel SHA-256 `1dedc1e0edd4aeff3af6addcebc274b9339e43033da06902bdeedabb6aa3710c`。

兼容/升级/回滚：内部 Trace Application/游标 Codec 增量，无公开 API、Schema/Migration 或历史数据改写；不装配页服务即可回滚。测试用合成密钥**不是**正式来源；目标运行账户专用密钥供给/备份恢复、通用 ResourceVersionRef→Owner Scope 解析、HTTP/浏览器/性能、Server2025/Debian、正式 License/法律、UAT/Gate/发行包尚待。
