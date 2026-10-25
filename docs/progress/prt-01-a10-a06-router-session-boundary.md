# PRT-01-A10-A06 Prototype Router、导航与会话边界

日期：2026-10-08
状态：`PRT_01_A10_A06_ROUTER_SESSION_BOUNDARY_PASS`

```text
前置任务：PRT-01-A10-A05-P04 PASS，A05全部结构化页面完成
涉及模块：App Router、AppShell、ProjectDetail、SessionClient会话变化通知、Prototype七类页面
涉及实体：无新增实体
涉及API：无服务端API变化；前端SessionClient增加进程内订阅通知
涉及权限：项目入口仍由当前Project授权控制；GLOBAL管理页仅DeploymentAdmin读取；服务端逐请求重证不变
验收标准：八个命名路由、项目/管理员导航、会话失效退出、迟到响应/待恢复输入卸载、完整前端回归
风险：动态路由误入404、静态加载放大主包、登出后保留私有表单、前端提示被误作授权证明
```

## 实现结果

- 注册Prototype列表、详情、Version列表/详情、Package、PROJECT Template、Link及GLOBAL Template共八个
  命名路由；既有页面内RouterLink全部由真实Router解析，不再依赖测试占位路由。
- ProjectDetail增加“项目原型、固定版本与需求覆盖”入口；AppShell部署管理导航增加“全局原型模板”。
  管理入口可见不代表授权，Global页面在非DeploymentAdmin时不发Template/Document读取请求。
- 七类Prototype视图使用动态导入，避免把本轮全部页面加入初始主包。生产构建形成独立页面chunk；主chunk
  仍有既有大于500 kB警告，但没有因A05页面注册增长到静态加载后的892.25 kB。
- SessionClient新增仅进程内的revision/subscribe通知。登录、current、renew、logout及Prototype写401导致本地
  身份失效/替换时通知AppShell；当前业务路由立即替换为Login，卸载页面后其既有generation守卫会丢弃迟到
  响应并清除pending输入。订阅不包含Token/CSRF，也不能授予权限。
- 项目角色、License和对象权限仍由服务端每次请求重证；403/404业务拒绝不被前端伪装成整个Session失效，
  页面刷新会清除旧读取结果。前端路由/导航只是安全提示与状态清理，不是授权边界。

## 验证、兼容与回滚

- 定向4文件/200项覆盖八路由解析、项目/管理员导航、Session invalidation/替换/unsubscribe、Prototype写401
  退出及既有ProjectDetail回归；Windows 11前端全量101文件/1599项、typecheck、Vite 220 modules生产
  构建通过。Prototype页面已拆分独立chunk；既有主chunk警告保留。
- 无Schema/Migration、服务端API、依赖、角色、Secret、客户数据或外发变化。升级只需重建前端静态资产；
  回滚移除路由/导航/订阅及恢复静态状态即可，服务端与业务历史不变。
- 当前不声称真实Edge/PG闭环、Windows Server 2025、Gate 3、UAT或发行通过；A07执行Windows 11真实闭环，
  Debian 13按用户指令跳过。
