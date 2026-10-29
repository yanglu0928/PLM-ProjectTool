# CR-EXEC-031：修正 PlanVersionReadClient 原生 fetch 接收者

- 日期：2026-10-29
- 状态：已预先登记；待实现与托管验证
- 证据：A17 hosted Windows run 40835305470 创建返回 201，但固定详情 GET 未发出，UI 显示 PLAN_VERSION_READ_UNAVAILABLE。按 CR-EXEC-030 在 Edge 中用窗口级 wrapper 绑定 window 后，run 40837248488 的 PlanVersion 固定 GET 返回 200 两次，应用自动跳转 UUID 详情路由。与源代码 PlanVersionReadClient.get 保存自由原生 fetch、随后以 this.fetcher(...) 调用一致。
- 问题：浏览器 Fetch API 的接收者被错误绑定至 Client 实例，原生 fetch 在请求发出前拒绝；异常被 catch 映射为通用读取不可用。固定版本列表与详情读共享此路径。
- 范围：只调整 apps/frontend/src/modules/plan/api/planVersionReadClient.ts 的 fetch 调用接收者，并在同模块单元测试中增加接收者回归；同步调整 A17一次性浏览器等待条件，既允许页面快速自动跳到详情，也继续要求真实Create=201、固定GET=200和详情快照可见。无API、Schema、权限、许可或业务状态变更。
- 实施：通过 Reflect.apply(fetcher, globalThis, [path, init]) 调用，保持注入的 fetcher 兼容且使浏览器原生 fetch 具有 Window 接收者。A17验证不再依赖短暂 CreateView 成功提示，等待 UUID详情路由及固定快照内容。
- 迁移/兼容：无数据库、持久数据、API合同或安装迁移；列表和详情读取现按平台标准调用 fetch。
- 风险：错误接收者上下文测试可能受 Node/Vitest 全局差异影响；应以 this === globalThis 定向验证，并通过前端全量套件/TypeScript构建与包内 Edge验收。
- 回滚：恢复 this.fetcher(path, init) 并移除新增接收者断言及 Harness路由条件；不涉及数据回滚。
- 验证计划：定向前端单测及全量/构建均在 GitHub hosted Windows 执行；完整 A17父包同提交重建，D盘解包与临时PG，Edge创建、固定GET、Validate=0、送审与PG Audit/Receipt/Review/Round一致、Decision=0，资源清理及候选摘要复核。
- 约束：仅托管runner运行项目代码，不在用户本机/C盘执行；所有数据为合成数据；Pilot/Gate/Release仅由客观证据决定。
