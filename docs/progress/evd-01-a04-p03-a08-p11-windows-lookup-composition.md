# EVD-01-A04-P03-A08-P11：资格操作回查 Windows 显式组合

日期：2026-10-01；Phase 2 Platform Core；结果：`WINDOWS_SYNTHETIC_COMPOSITION_PASS / FRONTEND_AND_BROWSER_OPEN`。

编码前检查：输入 CR-EVD-004、API 非 Breaking 增量、P07～P10 的已验收收据/权限/内部服务/可选 HTTP；前置满足。任务只在现有 Windows `--platform-write` 组合中注入 Evidence 回查服务和 Router，复用当前 UOW、Session/CSRF、License、项目授权及收据；不改变 ORM/Migration、冻结路径、角色、依赖或默认启用范围。验收包括写组合真实数据库回查、未知操作号、无权/降权/License拒绝、登录专用及只读模式关闭，及后端回归/构建。风险：隔离合成身份及本机信任源不代表正式发行或跨平台。

Windows 11 全新临时 PostgreSQL 18/pgvector 中，显式写组合完成 Evidence 创建→人工资格 POST→原操作号只读回查 `COMPLETED`；不存在操作号只返回 `UNCONFIRMED`。外部项目成员 404、License 失效 403、角色降权 404；登录专用 404，只读组合无此 POST 方法（405），原 Evidence/Viewer/篡改/撤权回归通过。脚本退出 0，临时实例清理。Python 3.13 后端全量 1,814 项 PASS、3 项既有跳过；开发 wheel SHA-256 `a57f099c13bca75aae03da2d56c7e6336d362900d7182060c34eb3ffb66457f4`。

兼容：只在明确 `--platform-write` 组合增加已登记的 V1 非 Breaking 操作，默认应用、登录专用和只读模式不新增写能力。升级要求既有 `0015` 收据表及目标账户可信 License/HTTPS/游标密钥配置；无迁移。回滚为不注入可选 Router，历史 Evidence/Audit/收据保留。前端精确回查、真实浏览器、正式目标账户、Windows Server 2025/Debian 13 和 Gate 3 未验证，不能标交付可用。
