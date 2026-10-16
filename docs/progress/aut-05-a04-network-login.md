# AUT05A04 实际网络登录链

2026-09-27 / 0.1.0.dev0 / REAL_NETWORK_AUTH_PASS / BROWSER_PENDING。

编码前：Phase2/AUT05A04，前置A03代理原策略网络通过、A02页面63测试通过；输入原aut03a07p03生产登录验证/current0049/原Windows工厂/API。仅新验证适配器，将原真实临时PG/Vault fixture的TestClient传输换为实际Uvicorn/Vite/httpx网络，不mock实际Service/SQL/Session/Audit。

原fixture唯一临时库/角色/凭据/hash/Project/Audit断言和cleanup保持，Bootstrap allowed_origin只在本轮fixture显式设为自有Vite端口；原localhost正向请求在网络适配器映射至同一实际浏览器Origin，恶意Origin保原值。Vite配置保Host/Origin、无CORS，只test target指向自有Uvicorn端口；默认工厂与显式登录两context均走实际网络。不是生产配置或授权回退。

验收：原登录/GET/续期/退出/重放冲突/并发/DB计数全部实际网络通过，Cookie属性保留、错误来源/密码拒绝；默认404不变，原Migration/head真实。自有Uvicorn/Vite按上下文关闭后fixture清临时DB/角色/Vault，不kill用户服务。无新API/Schema/依赖/后端实现。

风险：多线程与进程生命周期/端口重用/未知提交，不忽略失败或重跑覆写结果；5秒网络超时与有界启动/停止，停止必须已实际退出才清库。日志关闭，不输出body/连接串/Cookie/CSRF。明确合成账户，未测真实浏览器/UI/HTTPS/生产信任、20并发性能、全应用。回滚撤新适配器保原ASGI验证与历史；Gate/CR008 FAIL/正式包待。

## 执行结果

原fixture所有断言已在实际网络执行，不修改原脚本：两个Uvicorn/Vite上下文，9 GET/12 POST，原default login/session404保持；正向真实固定Scrypt登录及项目摘要、恶意Origin403/错误密码401无Cookie、GET不含CSRF/不旋转Cookie、实际暂停成员后摘要空、renew更换Cookie/CSRF/保absolute期限、旧Cookie401、logout删除Cookie、同Key重放200/异Key401/新会话同Key冲突409、实际并发同Key退出双200与最终失效均通过。实际PG最终3Sessions、SESSION_ISSUED2/RENEWED1/REVOKED2、logout收据2，未mock Repo/Service/SQL或响应。

结束后额外查询原自有数据库/同名角色在pg_database/pg_roles各count0，原Vault target实际CredReadW不存在且Windows错误1168；本轮上下文Uvicorn线程join实际完成、Node进程wait完成，无用户进程/生产源删除。本轮清除的是可重建的合成临时库/角色/Vault来源，无客户资料或生产修改。固定允许的是本轮Vite Origin，正向旧localhost值在传输适配器明确映射，恶意Origin不映射；不是更改正式trusted_origins。

最终网络验证exit0。前端完整63/63/typecheck/build通过、36modules/JS100160/CSS4124。增加清理后核查与日志输出整理后，再完整网络复跑通过；首次输出仅应用安全元数据，普通logging.disable无法关闭独立StructuredLoggers，不改生产logger，而在验证进程将其写入临时内存流并丢弃，Uvicorn访问日志关闭、无body/连接串/Token输出或运行日志入Git。

Changed仅2新验证文件与记录，无后端实现/API/Schema/权限/依赖变动，兼容0049无升级。没有JS客户端/页面真实浏览器自动Cookie证明，本轮是httpx持有Cookie的本机真实HTTP；无HTTPS/Secure实际浏览器、生产信任/目标账户/全应用/20并发性能或完整包证明。后端unit/coverage/wheel未重跑；CR008 FAIL/Gate保留。

下一AUT05A05：中文页面真实浏览器交互/布局、自动HttpOnly Cookie、刷新只读与重登、续期/退出及失败提示；仍用自有临时合成源并严格清理，正式信任/TLS另验。原数据库审计计数不能因浏览器附加操作被静默放宽，需独立浏览器fixture与验收。
