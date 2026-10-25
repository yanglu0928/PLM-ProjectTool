# CAP-02-A05-P04-P03-A04-P02-A02：固定内容 HTTP/Windows/PG

日期：2026-10-24；结果：`WINDOWS_11_SYNTHETIC_HTTP_PG_PASS / UI_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P04-P03-A04-P02-A02`，仅把已通过内部服务做 Review 作用域 GET、签名分页和 Windows 写模式装配。|
|基线/前置|`CR-CAP-006` 已先登记；A01 内部同事务资格/绑定重证通过；原 Gate 2 PROJECT API/Capability 普通目录不变。|
|模块/实体/API|Review API、Capability Windows 组合根、应用工厂可选 Router、隔离验证夹具；无 ORM/Migration/新依赖。新增两条 GET，默认及 Windows 只读模式不装配。|
|权限/风险|每次服务调用重验当前 Session/License/当前启用与受分配身份、精确 Review/Version；游标 HMAC 域隔离复用已有 Capability child key，绑定 Session/Review/Version/页大小；页间状态变化拒绝。|
|验收|默认404、固定版本/两页真实 HTTP、未分配/停用/失效许可/跨会话/篡改游标拒绝、Review 决定链仍工作，独立合同与全量回归、临时库/服务复位。|

Windows 11 本机隔离 PostgreSQL 18.6 合成夹具从 GLOBAL 文档/Evidence 建立双条目 Capability Version、校验、送审，普通受分配 Reviewer 读取固定 Version 和两页条目及文档版本引用，再验证拒绝矩阵、逐人决定和最终批准；不外发客户数据。默认应用及只读组合不开放。独立合同/组合定向 7 项、15 子例；后端全量 4095 通过/3 跳过/6149 子例，2 个既有警告。迁移检查无新增升级操作。测试临时库 0，PoC PG 服务从停止态临时启动并已恢复停止。

限制：仅合成 Session/License/游标密钥的 Windows 11 HTTP/PG，不是正式发行信任或真人核对/批准；前端页面、Edge/固定包、文档正文授权跳转、离线安装升级、Gate/Pilot/Release 均未通过。Server 2025 与 Debian 13 未实测。
