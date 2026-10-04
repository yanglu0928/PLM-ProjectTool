# AUT05A03 同源代理实际网络测试

2026-09-27 / 0.1.0.dev0 / Windows11 Node24.17.0/pnpm11.19.0/Python3.13.15。

验证入口validation/aut-05-a03-same-origin-proxy/verify.mjs及probe.py。真实Vite→隔离loopback Python探针，调用原LoginOriginPolicy，六请求及默认target/changeOrigin/no-rewrite/cors=false断言通过、实际exit0；正确来源/GET/health418，恶意/缺Origin、直连后端Host与浏览器Origin不一致403。418不是认证成功，probe不返回Session/Cookie或业务数据。实际检查合成Cookie/CSRF/Key/body传递无变化及无CORS，测试target仅自有临时端口。

失败历史：Windows ESM路径启动失败，改pathToFileURL；次轮Vite默认CORS头不满足同源断言，记录后显式cors:false并完整复验。自有服务finally关闭/子进程退出，不kill用户服务。

完整前端63/63/typecheck/build通过，36modules/JS100160/CSS4124；后端unit/PG/coverage/性能/wheel未重跑。无后端/API/Schema/依赖变化，兼容0049无DB升级。FastAPI+PG登录/真实Cookie浏览器链未验，后续A04；正式trust/CR008 FAIL/Gate/包待。
