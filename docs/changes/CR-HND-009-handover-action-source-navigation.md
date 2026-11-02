# CR-HND-009：交接待办固定来源导航

- 日期：2026-11-02
- 状态：已登记，按既有持续授权执行；不改变 Gate 结论
- 关联 WBS：PLT-PKG-01-A09-P51-A50
- 来源：A50 前置审查发现 Action GET 只返回不可变来源版本 ID 与问题 ID，但没有父 Analysis ID；现有详情页面因此不能构造精确、可授权的来源路由。Survey 的来源定位和 Handover 的 Evidence Viewer 已证明按项目权限读取固定来源可行。
- 冲突/证据：冻结的 HND Action GET 投影没有 parent analysis identity；前端严格校验 DTO；HandOver 详情路由需要 Project + Analysis ID，固定版本只能通过 `fixedVersionId` 查询选择。不能从 action 的两个 ID 猜测父分析，也不能遍历项目分析列表或拼接本地路径。
- 方案：
  1. 改数据库/API Action GET 已有 DTO，增加父 Analysis ID：改动少，但会改变冻结响应形状并要求旧严格客户端兼容处理。
  2. 新增只读 Action 来源子资源，按当前已授权 Action 解析不可变来源链，返回受控的 Analysis/Version/Item ID；现有读权限重新验证，不写 DB、不改旧 Operation/投影。
  3. 不提供跳转，只展示来源 ID：安全但不满足用户已确认的待办直达原文位置诉求。
- 选择：方案 2。新增可选只读子资源 `GET /api/v1/projects/{project_id}/handover-action-items/{action_item_id}/source-location`，要求 Action GET 同等 Session、License、Project/member 读取授权；服务端从同 Project 的 Action → Version → Analysis Item 关系解析，禁止客户端传入/覆盖目标 ID。HUMAN 来源返回受控 UNAVAILABLE，不推造文档锚点。前端导航只使用返回的固定版本与问题 ID；目标页面对 Project/Analysis/Version/Item 再授权和严格核对。
- 差异与影响：新增一个可选、只读 V1 子资源及客户端交互；既有 Operation 和数据库 Schema 不变，无 Migration、依赖或配置变化。普通应用仍不挂载，只有显式 Handover Action read router 组合可用。
- 安全风险与控制：越权/跨项目/已失效来源泄漏；通过同等现有 Project 权限、项目条件 SQL、固定父版本一致性检查、统一隐藏 404、no-store 和后续目标 GET 复核降低风险。不返回正文、Evidence Locator、文件路径或下载 URL。
- 回滚：移除该只读子路由/客户端按钮和目标页的可选 source item 导航参数；既有 Action GET、业务记录和历史确认保持不变。
- 验证计划：云端 Hosted Windows runner 上运行后端读 Owner/API/Windows Composition 定向与全量测试；前端客户端/Action 工作台/HandOver 详情定向与全量 typecheck/build；托管 Edge 合成测试验证同项目跳转、跨项目拒绝、HUMAN 安全退化、失效版本/不存在 item 错误、列表翻页定位和动作后状态不丢。无客户数据；不进行本机代码运行、正式安装、服务启动、外部数据发送或 Gate 推定。
- 本次变更不替代真实 Windows 11 设备验收，不关闭 Gate 3、Pilot 或 Release。

## 云端验证偏差记录（修复前）

- 2026-11-02 hosted run 41390769460：前端 Vitest 200 个文件/2,075 项通过；TypeScript 检查发现新增 Handover 目标锚点测试在 `DOMWrapper` 上调用类型不提供的 `.exists()`，造成构建失败。这是验证断言与组件测试库 API 的不兼容，不是运行时产品功能缺陷。
- 影响：仅阻断该提交的前端 typecheck/build；当前证据不能标记 A50 通过。后端全量验证仍进行中。
- 修复：只改测试断言为读取定位元素的 `id` 属性并与合成来源 Item ID 比对；不改产品逻辑、API、Schema、权限或用户数据。回滚可恢复原测试文本；无需迁移。
- 复验：记录此偏差后，提交测试修正，重跑 GitHub hosted Windows PR 完整流水线，要求全量前端 tests/typecheck/build 与后端全量测试/wheel 成功；保留失败 run 和修复后 run 链接。
