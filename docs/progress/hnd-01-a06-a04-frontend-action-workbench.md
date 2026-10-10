# HND-01-A06-A04：Handover Action 只读待办工作台

日期：2026-10-05。结论：`HND_01_A06_A04_FRONTEND_ACTION_PASS`。下一项：`HND-02-A05-A01` Action 七个写 Operation 的 HTTP/组合前置核查。

## 实施结果

新增 Action LIST/GET 严格前端客户端及项目级只读待办工作台。客户端校验不透明 cursor、强 ETag、来源形状、状态/时间、人工输入字段、响应 DocumentVersion、Evidence 用途及当前状态事件；任何父事实、序号、状态或响应形状不一致均失败关闭。

工作台明确显示 `OPEN → IN_PROGRESS → SUBMITTED → VERIFIED → CLOSED` 语义，其中 SUBMITTED 固定显示“已提交待验证”，VERIFIED 固定显示“已验证待关闭”；缺验证、关闭时间或 Resolution Trace 时绝不显示完成。详情把 `requested_input_spec` 转成名称、必填性、格式和示例提示，不提供伪写表单。

响应文档只导航到 Document Owner 页面。提交/验证/解决 Evidence 只有用户点击时才调用 Evidence Viewer 重新验权并定位固定版本；初始列表与详情不复制原文。项目详情增加待办入口。

## 客观验证

- Action客户端 16 项，页面新增3项，连同项目导航定向共37项通过；覆盖cursor/ETag、严格来源、输入规格、响应/Evidence顺序、当前事件、SUBMITTED非CLOSED、安全错误、无身份/改密关闭、按需Evidence定位。
- 前端全量74个文件、1315项通过；TypeScript typecheck和Vite production build（160 modules）通过。
- 主JS `539.06 kB` 超过Vite默认500kB提示；构建成功。该增量强化了既有按路由动态拆包的发行性能必要性，不在本任务静默改造全局路由。

## 兼容、回滚与未关闭项

纯前端客户端、页面、路由和导航增量；无Schema、Migration、后端API、依赖、Secret、外发或客户数据变化。撤页面/客户端即可回滚，业务历史不变。

Action CREATE/PATCH/START/SUBMIT/VERIFY/CLOSE/CANCEL 仍只有内部Owner，没有公开写HTTP或前端动作；下一任务先完成严格HTTP与Windows组合。真实浏览器、路由拆包性能、正式信任、Gate 3、UAT和发行仍开放。
