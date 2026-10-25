# AUT-05-A02 登录与当前身份页面

2026-09-27；0.1.0.dev0；状态PAGE_COMPONENT_PASS / LIVE_BROWSER_PENDING。

编码前检查：Phase2；WBS AUT05A02；前置A01客户端52测试/typecheck/build通过，冻结API01/02及CR-AUT007保持。仅Auth前端页面及路由导航，实体安全SessionView；四原接口，不改变服务端授权/API/Schema/依赖。验收为中文可操作登录/当前身份/续期/退出、刷新只读重登提示、受限提示、单提交与密码字段清理，组件/路由测试及完整前端构建。

风险：客户端不能提供真实权限，受限用户改密页面尚缺，不暗示可进入业务；网络失败本地清身份不宣称服务器退出；卸载后异步响应不得更新页面。浏览器密码字符串不能保证物理擦除，只清表单引用，不持久化/日志。恢复仅显式用户点击，不自动登录或续期。使用原Client生成随机logout Key，不重试，不存Token。

同源/API开发代理和实际后端/浏览器单独后续验证，本轮不开放CORS或改变可信Origin。无DB/Migration/依赖/后端变更，回滚撤页面/路由恢复壳；Gate/性能/正式材料仍待。

## 实际结果

新增/login中文页面与主导航入口，原首页/404保留；显式登录/查询/续期/退出通过真实SessionClient接线，没有自动身份查询、登录或续期。form label/密码autocomplete/required、按钮pending禁用与重复submit保护、action同步取输入后立刻清密码，失败隐藏旧身份且只显示固定安全错误；异步结果在卸载后丢弃。退出成功仅在客户端确认revoked后显示，故障不称已退出。刷新/离开页面丢内存CSRF时提示重登，受限身份不显示管理或项目权利，明确改密页面尚待。

首次61测试5失败：传入SessionClient被Vue props递归代理，JS私有字段brand拒绝使请求未发出；修复仅通过toRaw解包客户端，保持私有Token而非取消私有字段/降低错误检查。完整61/61/typecheck/build后，再补服务器显示字符串HTML逃逸与真实AppShell/login路由无自动Auth请求两项，最终完整63/63/typecheck/build通过。新11用例（组件10/真实路由1）+原52；旧导航测试只由1更新为已实现的2，不添加未实现业务入口。

Windows11/Node24.17.0/pnpm11.19.0；实际产物36modules、JS100160bytes/CSS4124bytes，页面和client现在被入口导入；相较A01不再是未引用文件。没有真实浏览器可视检查/HTTP后端集成、后端unit/PG/coverage/性能/wheel复验，fetch成功仍为契约模拟，不将jsdom或build当生产可用证明。

版本兼容0049，无DB升级/API/后端/依赖变更。已知：改密页面未接，Vite目前只有health代理，正式trust/TLS/目标账户缺项与CR008性能FAIL保留；Gate/完整包未完成。下一AUT-05-A03：同源开发Auth链前置及实际可信Origin/Host与代理验证；不使用CORS、假Token或生产信任回退。浏览器视觉/真实用户流程随后补证。
