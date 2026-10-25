# AUT05A04 真实网络认证报告

2026-09-27 / 0.1.0.dev0 / Windows11 Python3.13.15/PG18/Node24.17.0/pnpm11.19.0。

validation/aut-05-a04-network-login/verify.py以原aut03a07p03真实Windows工厂/PG/Vault fixture替换TestClient**传输**为Uvicorn/Vite/httpx，不mock权限/SQL/Service；Bootstrap显式允许本轮Vite Origin，正向localhost请求Origin映射明示，恶意值保持。21实际HTTP（9GET/12POST）两上下文及原全部SQL/Cookie/CSRF/Session/Project/Audit断言通过，实际exit0。

覆盖：default404、恶意来源/错密码拒绝、真实登录/GET项目摘要/实际成员暂停摘要更新、续期Cookie/CSRF旋转与旧token失效、退出清Cookie/同Key重放/异Key拒绝/新会话原Key冲突、真实双并发退出，最终3Session/2issued/1renewed/2revoked/2logout收据。全部响应无CORS。httpxCookieJar不等于浏览器HttpOnly/Secure自动行为，真实页面/浏览器/TLS未测。

自有Uvicorn线程/Node服务退出后原fixture清理，额外真实PG查询仅本轮自有库/角色count0，实际Vault CredReadW缺项/error1168。清的是合成可重建资源，无生产/客户资料变化。补清理核查后完整网络重跑，最后整理StructuredLoggers输出至本进程临时内存流后再完整网络通过，不改生产日志/响应/断言。

完整前端63/63/typecheck/build通过，36modules/JS100160/CSS4124；后端unit/coverage/性能/wheel未重跑。无API/Schema/依赖/生产实现变化，兼容0049无升级；正式trust、CR008性能FAIL、Gate/可用包仍待。下一独立浏览器fixture保原计数验收，不偷改原SQL预期。
