# AUT-05-A03 同源开发代理

2026-09-27 / 0.1.0.dev0 / NETWORK_PROXY_POLICY_PASS / AUTH_BROWSER_PENDING。

编码前：Phase2/AUT05A03；前置A02页面/client63测试/构建，输入原API01/02、LoginOriginPolicy。只改Vite开发代理使固定/api/v1走原127.0.0.1:8000后端、保原Host/Origin/Cookie/CSRF，无重写/自动授权/CORS/forwarded-header信任。

验收：真实本机网络Vite→隔离探针→原LoginOriginPolicy，正确Host+Origin通过来源门、错Origin/Host拒绝，不把来源探针成功当登录；Cookie/CSRF/Key保留，健康代理保留，默认target不变，完整前端test/typecheck/build。目标服务必须显式配置浏览器来源http://127.0.0.1:5173，不能替其自动加入可信来源。

风险/回滚：开发代理不用于生产、端口被占不杀进程/不自动选生产端口；验证选择自有临时端口，仅测试target覆盖到本轮自有探针，策略仍原类、固定允许本轮Vite Origin。无正式认证/DB/客户资料/秘密/购买/外发。删除api代理即回滚，生产配置/API/Schema/依赖不变。真实PG登录/浏览器/TLS/正式trust另验，完整包/Gate未完成。

实施中发现：Windows ESM import必须pathToFileURL，首次脚本启动失败已修正；第二轮实际Vite向同源探针响应附加默认CORS头，原“无CORS”断言失败。先记录再设置server.cors=false，禁用无需的默认开发CORS，不扩大信任、不修改后端来源或生产配置，后续完整重跑。不把失败掩盖为通过。

## 实际结果

实际Vite服务与自有Python网络探针已运行，原LoginOriginPolicy非mock。六请求：正确POST来源418、恶意Origin403、缺Origin403、正确Host GET418、原health路径418、直连探针端口Host与浏览器Origin不一致403。418明确是探针，不是登录/会话成功；逐项断言原Host/Origin、未重写路径/body、合成Cookie/CSRF/Key保留、响应无CORS。固定默认target8000与changeOrigin=false/无rewrite/cors=false机器检查通过；测试target明确换为本轮自有临时端口，不接用户8000服务。

诊断实际exit0，原前端63/63/typecheck/build全部通过；产物保持36modules/JS100160/CSS4124。验证finally关闭本轮Vite并终止本轮自有探针子进程，不触及其他进程或DB。无API/后端/Schema/依赖改动，无DB升级；代理配置只影响开发环境。回滚可撤新api proxy/cors:false恢复旧开发壳，旧CORS行为历史保留，推荐保关闭CORS。

backend配置须显式将http://127.0.0.1:5173列入trusted_origins，localhost与127.0.0.1及不同端口不互换；Host+Origin严格一致，不能开启changeOrigin以规避检查。使用HTTP仅限loopback开发，正式同源HTTPS部署另验。

当前没有FastAPI login/真实PG/Cookie浏览器生命周期证明，后端unit/coverage/HTTP性能/wheel未重跑；原A41/A40证据保留，CR008 FAIL/正式trust/Gate/完整包未完成。下一AUT05A04：真实PG临时库/Windows显式Login工厂→Uvicorn→Vite的本机网络登录/Session/续期/注销，明示合成输入与原正式信任缺项；浏览器视觉/交互随后补证。
