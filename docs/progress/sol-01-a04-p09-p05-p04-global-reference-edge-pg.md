# SOL-01-A04-P09-P05-P04：GLOBAL Reference Edge/隔离 PG 读取链

日期：2026-10-09；结果：`GLOBAL_REFERENCE_EDGE_PG_PASS`，限定 Windows 11/一次性 PG18.6/合成资料与脚本交互。Gate 3/UAT/正式客户确认不因此通过。

编码前检查：Phase 2；前置 P09-P02～P04 服务端 GET/List 和 P05-P02/P03 前端已通过。仅扩展现有一次性 GLOBAL 来源/Edge 夹具，显式装入 CREATE/GET/LIST；不修改正式业务代码、Schema、公开 API、License 或角色。验收要求真实登录、固定来源 Create→详情与列表、受权文档下载、GLOBAL Evidence Viewer、失去 Session 后失败关闭及原多/单来源回归。

实测：一次性隔离 PG18.6、真实 Session/ASGI、独立 Edge 临时 Profile。两条固定 GLOBAL Document/Evidence 来源经浏览器核查后合成创建，Create201/原子 Reference/Audit 实存；点击创建后详情，GET200 呈有序文档版本并通过受权版本下载200，Evidence Viewer200 给出定位和内容链接；候选列表 GET200 能再次打开对象。移除 Session Cookie 后重新读取详情 401，历史内容链接消失。浏览器脚本先有两次断言错误：把 aria-label 当页面正文等待、以及切换路由时过早点击；改为 DOM/路径就绪检查后同一隔离链重跑退出0。原多/单来源 Create/Confirm/Revoke/原 Key 回查验收再跑退出0，避免新模式改变旧测试。

限制：本轮浏览器勾选仅用于自动化合同，不是客户真人脱敏确认；Evidence Viewer 提供位置说明和原文下载，未提供浏览器内精确高亮。撤回后历史 GET 已由 P09-P03 独立 PG 验证，不把本轮新 Edge 模式误称为撤回后的浏览器验收。真实 PG 双页、正式 License/目标账户密钥、Server 2025、20 并发、Gate 3/UAT/发行仍待；Debian 13 依用户指令跳过。

兼容/迁移/回滚：仅验证夹具，既有脚本默认模式不变；无数据迁移。删除新验证模式/目录可回滚，不删除业务数据。TraceLink：API-04 → P09-P02～P04 → P05-P01～P03 → 本 P05-P04。
