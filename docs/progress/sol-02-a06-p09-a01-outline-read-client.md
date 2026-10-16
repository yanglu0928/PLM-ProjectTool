# SOL-02-A06-P09-A01 方案大纲前端只读客户端

日期：2026-10-09。状态：前端读取合同通过；尚未挂页面或浏览器实测。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-02-A06-P09-A01。
- 输入基线：冻结 `SOL_OUTLINE_LIST/GET`；P08 Windows 显式平台读取组合；现有 PROJECT Reference 前端传输惯例。
- 前置任务：P01～P08 Owner、HTTP/游标及 Win11 隔离 PG/ASGI 验证通过。
- 模块/实体/API/权限：Solution 前端 API 层；SolutionOutline 身份/批准指针；冻结列表/详情 GET；同源 Session Cookie，服务端逐次 License/项目成员复验。
- 验收标准：严格校验项目/对象 ID、摘要/详情固定字段、空或合法批准指针、UTC 时间、强 ETag、升序页及独立签名 cursor 形态；只映射已知服务端错误，同源无缓存请求，不在客户端宣称批准事实。
- 风险：无 UI 时不可作为可操作功能，目标账户游标 key/正式信任源及浏览器仍待。

## 实施与验证

新增 `OutlineReadClient`、不可变列表/详情 DTO 与严格解析器。详情要求响应 ETag 与正文一致；列表要求固定字段、升序、不重复、合法后继游标。所有请求使用同源凭据、no-store、禁止重定向和超时取消。未修改后端、Schema/Migration、冻结 API 或依赖；移除客户端可回滚。

- 定向前端：4 passed。
- 前端全量：110 files / 1651 tests passed；`vue-tsc`、Node TypeScript 与 Vite build 通过。既有主包 >500 kB 构建警告保留，未将其视为本切片验收失败。
- 真实浏览器/PG：本切片未运行，不能标 UI/UAT PASS。

下一项：`SOL-02-A06-P09-A02` 方案大纲列表/详情页面与路由；随后创建入口、创建后定位和真实浏览器/隔离 PG 链。
