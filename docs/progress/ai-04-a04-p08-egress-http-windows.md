# AI-04-A04-P08：Windows 11 / PostgreSQL 18 Egress HTTP 组合

- 日期：2026-10-03
- 结果：PASS（隔离合成信任与策略；无真实外发）
- 依据：CR-AI-013、DEC-709～712、AI-04-A04-P07

新增关闭默认入口的 Windows Egress 组合工厂。工厂只有在调用方显式提供 DatabaseRuntime、Session、License Guard、Audit、Document Owner、版本化 Preview Policy 和部署 Approval Policy 时才创建 Router；没有将路由挂入默认、登录、只读或当前生产写组合。正式策略来源缺失时因此继续失败关闭。

为兼容冻结 GET 无 CSRF、写操作强制 CSRF 的合同，新增 Egress Session 适配器：GET 使用项目读 Session 共享锁验证，Preview Create/Authorize/Revoke 使用项目写 Session+CSRF验证。组合使用真实 ProjectAuthorization、DocumentVersion AI Input Owner、PostgreSQL Preview/Authorization 仓储和持久幂等/Audit。

Windows 11 本机 PostgreSQL 18.6 隔离验证实际执行：默认404；真实Session/ProjectManager/DocumentVersion来源创建Preview 201和同Key重放；GET安全投影；非成员/跨项目404；Authorize 201和同Key重放；Revoke 200和同Key重放；撤销后原Authorize Key仍返回首次`AUTHORIZED@0`，数据库当前根保持`REVOKED@1`；License拒绝403。数据库只形成1组Preview/Source、Authorization/AuthorizeResult、Revocation/RevokeResult，3份Egress Audit和3份完成收据。

首轮验证在Authorize同Key重放得到503。原因是P07 HTTP边界要求数据库保存的首次trace等于重放请求的新trace；修复为保留业务结果原trace、不将其与当前响应envelope trace比较，合同Fake也改为独立trace并完整重跑。此修复不放宽授权、项目、幂等、版本或审计检查。

验证结果：P07合同5项 PASS；P08隔离脚本退出0并删除临时数据库；后端全量2130项运行、3项既有环境跳过，零失败；开发wheel SHA-256 `d1533684503661409b357c5a567091bd01acab693b4da4b0f2645e75f2fff093`。

边界：License Guard、Preview Policy和Approval Policy为测试显式注入的合成控制，不是正式生产信任/策略来源；未连接Provider、未发送客户数据、无Schema/Migration/依赖变化。Server 2025、Debian 13、正式平台写组合、Gate 3/UAT/可使用程序包尚未由本项关闭。
