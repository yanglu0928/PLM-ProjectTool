# SOL-02-A06-P09-A03 方案大纲安全创建前端

日期：2026-10-09。状态：前端合同/全量测试、类型检查与构建通过；真实浏览器/隔离 PostgreSQL 待下一项。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-02-A06-P09-A03。
- 输入基线：冻结 `SOL_OUTLINE_CREATE`，后端 A03～A05 创建及 P01～P08 读取；P09-A01/A02 严格只读客户端和页面。
- 前置任务：后端真实 Session/PG 合成创建与 LIST/GET、前端读取合同已通过。
- 模块/实体/API/权限：Solution 前端、会话安全传输白名单、路由；SolutionOutline；复用 `/api/v1/projects/{projectId}/solution-outlines` POST。仅项目负责人或实施成员显示创建入口，服务端继续最终授权。
- 验收标准：仅名称请求、NFKC/trim、原操作号先于发送保存在会话存储；严格 201 投影、ETag、Location、Trace；成功定位详情；不确定结果不换键、不自动重试；刷新后只在明确确认下同键恢复；存储失败停止发送。
- 风险：实际浏览器/PG 尚未联测；正式目标账户信任源、Server2025、性能、Gate 3/UAT/发行未验。

## 实施与验证

新增安全创建客户端和页面，沿用 SessionClient 的 Cookie/CSRF/Origin 请求路径。前端严格校验响应与请求项目、名称一致；仅服务端 201 的 Location、ETag、Trace 同时匹配时跳转详情。浏览器会话存储按用户/项目隔离保存原名称与幂等键；存储不可用或记录损坏时拒绝发送。未知响应/网络超时保留原记录，用户显式勾选后才允许同键重试。目录创建仍不表示方案正文或批准完成。

无 Schema、Migration、冻结 API 或依赖变化；撤下新路由/入口与客户端可回滚。会话存储中的未确认记录须先核对，不能用新键重新创建。

- 客户端定向 4，页面定向 3，通过；覆盖角色、CSRF/原键、严格响应、存储失败、刷新同键恢复及详情定位。
- 前端全量 113 files / 1661 tests passed；`pnpm build`（含 `vue-tsc`/Node TypeScript）通过。既有主包 >500 kB 警告保留。
- 测试中首次路由断言早于异步懒加载完成，改为等待路由完成；全量复跑通过。真实浏览器/PG 未运行，不计为 UI/UAT PASS。

下一项：`SOL-02-A06-P09-A04` Windows 11 真实浏览器/隔离 PostgreSQL 创建→详情→列表合成联测，覆盖授权、幂等恢复和拒绝路径。
