# HND-01-A06-A02：Handover Analysis 五读严格前端客户端

日期：2026-10-05。结论：`HND_01_A06_A02_FRONTEND_READ_PASS`。下一项：`HND-01-A06-A03` Analysis 列表/详情/版本/问题卡片页面。

## 实施结果

新增未接页面的 `HandoverReadClient`，覆盖 Analysis LIST/GET、Version LIST/GET、Item LIST 五个冻结 GET。所有请求固定 same-origin、`no-store`、拒绝跳转、JSON Accept 和 10 秒有界超时；项目/Analysis/Version ID、页长和不透明 cursor 在发网前校验，三类 cursor 使用 TypeScript 品牌类型保持调用族隔离，不在浏览器解码或持久化。

客户端对白名单 DTO、父级 Project/Analysis/Version 绑定、强 ETag、时间/状态/计数、分页形状与服务端排序执行失败关闭校验。Version 列表明确只接受计数摘要和折叠来源，Version GET 才要求 `source_documents/ai_tasks` 与声明计数一致，避免把列表误当详情。

Item 只保留六类业务问题、安全正文摘要、Evidence/Capability 引用和服务器状态。`NEED_CONFIRM` 必须同时具备确认问题、建议、至少两个选项及 1～32 个字段提示；字段提示严格投影 `name/format/example/required`，其余类型必须没有确认问题、选项和输入规格。客户端不读取原文、不调用 AI、不确认事实，也不开放写操作。

## 客观验证

- 定向 27 项通过：五条路径、三类 cursor 透传、父级绑定、摘要/详情区分、NEED_CONFIRM 维护字段、Evidence 引用、排序/重复/ETag、非法 ID/页长、安全错误、内容类型与超时。
- 前端全量 70 个文件、1288 项通过；TypeScript typecheck 和 Vite production build（149 modules）通过。
- 首轮测试发现列表方法参数错误为同步抛出，与既有异步客户端语义不一致，已统一为 rejected Promise；响应夹具复用已消费 Response 也已修正。随后复核真实 DTO，补充 Version 列表折叠来源与详情完整来源的区别，并完整重跑通过。

## 兼容、回滚与未关闭项

纯前端新增，未接路由或页面；无 Schema、Migration、后端 API、依赖、配置、Secret、网络外发或客户数据变化。删除未引用客户端即可回滚。

A03 页面、Evidence Viewer 点击定位、项目导航和真实浏览器尚未完成；Analysis 写 UI、Action 只读/写 HTTP 与 UI、正式 key/信任、Gate 3、UAT 和发行仍按总状态跟踪。
