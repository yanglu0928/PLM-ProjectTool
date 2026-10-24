# SOL-03-A05-A03-P05-P03：OutlineVersion 历史 Win11 Edge/PG 验收

日期：2026-10-09。结果：`SOL_03_A05_A03_P05_P03_OUTLINE_VERSION_BROWSER_PASS`；限 PROJECT 来源的真实浏览器页面链，GLOBAL 浏览器页面未实测。

编码前检查：Phase 2；输入 P05-P01 客户端、P05-P02 页面、P03/P04 真实后端/Windows 工厂及 Win11 可弃 PG18.6，前置满足。仅修复 Solution 前端客户端原生 fetch 调用方式、增加回归和一次性浏览器验收脚本；不变更 Schema/Migration、后端 API、权限或依赖。

真实 Edge 独立临时配置目录、合成 CUSTOMER_MEMBER 登录、真实 Session/PG18.6/Windows 读工厂和生产构建静态文件：从目录详情进入版本列表、查看 v2 DRAFT 与 PROJECT 固定详情，观察版本 LIST/GET 均 200，跨项目页面不展示版本；脚本完成后释放 HTTP 服务和临时 Edge 配置。真实浏览器暴露原生 `fetch` 被作为客户端方法调用时 `this` 绑定错误，mock 单测未发现；改为局部函数调用并增回归。首轮整页跳转丢前端内存会话、第二轮脚本误用 GLOBAL 断言，均属验收脚本问题，修正后通过。后端先前双 Scope P03/P04 仍有效，但本项浏览器只验 PROJECT。

验证：真实 Win11 Edge/PG 脚本退出 0；前端全量 126 文件/1725 项、typecheck/build 通过。浏览器没有模拟跨项目身份直接请求的后端 404，后端跨项目拒绝证据仍以 P03/P04 为准。不宣称 GLOBAL 详情浏览器、正式服务账户/Server2025、20 并发或 Gate3/发行通过。下一项转入 `CR-SOL-018` 的管理员审定 GLOBAL 非敏感标签与项目候选读面；Gate3/发行 BLOCKED。

TraceLink：Gate2 API-04 → A05-A03-P01～P05-P02 → 本浏览器验收 → CR-SOL-018。
