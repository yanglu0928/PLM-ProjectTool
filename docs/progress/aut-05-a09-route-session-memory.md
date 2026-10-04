# AUT05A09 路由间会话内存连续性

2026-09-28 / 0.1.0.dev0 / PASS（应用壳内存生命周期合同）。

编码前检查：Phase2；WBS AUT05A09；输入现有AppShell/LoginView/SessionClient、冻结Session Cookie+仅内存CSRF规则、A05真实浏览器刷新只读证据；前置Gate2/A05已满足，A08-P02浏览器改密提交缺口与本任务独立。模块前端Auth/AppShell内部依赖注入；实体无、API无新增、权限仍只由服务端实时校验。验收：同一AppShell内登录后路由离开/返回仍共享同一客户端与私有CSRF，表单可按原约束继续；重建AppShell模拟刷新后无CSRF/身份，不读取Cookie或storage自动恢复写权限；独立LoginView注入测试兼容，前端test/typecheck/build通过。风险是共享对象可能被Vue代理触碰私有字段，统一`toRaw`；内存会话不是授权缓存、不自动读取`GET session`。回滚撤provide/inject，恢复每页新客户端但重新出现跨路由丢写能力；无Migration/依赖升级。

L2决定：在AppShell每次实例化时新建唯一SessionClient并用Auth专属InjectionKey提供给后代。LoginView仍允许测试显式注入client；页面mount时只从同一客户端读取安全投影，绝不为保持状态写入浏览器持久存储。未来其他页面仅可调用客户端公开方法/服务器API，不能取私有CSRF。

Changed：AppShell实例级提供一个SessionClient，LoginView优先测试prop、其次注入、最后独立fallback并`toRaw`；页面重新挂载从客户端读取安全身份与当前可提交状态。没有新增全局单例、storage、Cookie读取或自动网络请求，也未将CSRF暴露给其他页面。既有改密未知结果Key仅存LoginView组件，离页会清除并要求管理员核对，跨路由共享客户端不改变此约束。

Tests：前端86/86、类型检查、生产构建PASS。新增AppShell路由测试从真实LoginView登录，再导航首页/返回，身份和写表单仍可见，登录仅调用1次且无自动Session GET；卸载AppShell并新建实例后身份/写表单均不存在。独立LoginView的显式client测试全保留。未运行本项真实浏览器/PG、后端全量unit/coverage；此内存状态不是服务器授权或生产部署证明。无Migration/API/权限/依赖变化。
