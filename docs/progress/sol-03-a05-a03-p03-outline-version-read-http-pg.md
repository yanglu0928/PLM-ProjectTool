# SOL-03-A05-A03-P03：OutlineVersion 历史 GET/LIST 真实 ASGI/PG

日期：2026-10-09。结果：`SOL_03_A05_A03_P03_OUTLINE_VERSION_READ_HTTP_PG_PASS`，范围仅 Windows 11 可弃临时 PostgreSQL 18.6 与真实 ASGI；正式 Windows 服务组装未开放。

编码前检查：Phase 2 / 本 WBS；Gate2 API-04、已验 A05-A02 内部 Owner、A05-A03-P01 游标、P02 可选 HTTP 合同均具备。只新增复用既有 PROJECT/GLOBAL 双 Scope 夹具的验证脚本，不修改程序、Schema、Migration、API/角色。原案无不兼容偏差，故无新 CR。

脚本先运行原有真实创建/来源证明和内部历史仓储/Owner 验证，再以真实 SessionService、SQLAlchemy UOW、PG18.6、TestClient 组装可选读取路由：PROJECT 两版本倒序页及跨页游标、GLOBAL 单版本，固定 Section/Requirement/Reference 详情；检查当前成员可读、跨项目/未知版本不可见、无效 Session 401、不可信 Origin 403、License 拒绝 403、跨页大小游标 400、只读 POST 及默认未注入 GET 404。执行退出 0，打印 `SOL_03_A05_A03_P03_OUTLINE_VERSION_READ_HTTP_PG_PASS`；Alembic drift 检查无新升级操作，既有表达式/计算列告警不代表本项漂移。

本项没有新增应用代码，P02 全量后端 3466 通过/3 跳过/5328 子例的结果仍适用；未重跑后端全量。不宣称 Server 2025、Debian 13、正式密钥 Vault/恢复、Windows 服务或浏览器通过。下一项 `SOL-03-A05-A03-P04` Windows 组合与独立游标密钥来源/恢复，随后前端/浏览器。Gate3/发行仍 BLOCKED。

TraceLink：Gate2 API-04 → A05-A02 Owner → A05-A03-P01/P02 → 本真实 ASGI/PG → P04。
