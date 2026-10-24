# HND-01-A05-A08：交接读取客户端原生 fetch 调用修复

日期：2026-10-24；编码前状态：`IN_PROGRESS`。

|检查项|结论|
|---|---|
|Phase / WBS|Phase 2 / `HND-01-A05-A08`；只修复交接读取客户端对浏览器原生 `fetch` 的调用上下文|
|输入基线|冻结 `/api/v1` 不变；`PKG-PILOT-01-A04-P03` 固定候选真实 Edge 首轮/复验均在交接页面报读取失败，登录、项目与后续调研/需求/原型/方案/计划及 Workflow 的浏览器响应为 200|
|前置检查|交接客户端 `#get` 唯一使用 `this.fetcher(...)`；相邻调研/需求客户端先赋值到局部 `fetcher` 再调用。真实 Edge 交接失败时没有交接接口响应，指向调用前失败；现有 mock 测试未检测 `this` 绑定|
|模块、实体、API|仅 `apps/frontend/src/modules/handover/api/handoverReadClient.ts` 及其回归测试；无后端、数据库、实体或冻结 API 更改|
|权限/验收|不改会话/CSRF/License/项目隔离；定向测试必须模拟浏览器原生函数所要求的调用上下文，前端全量测试/typecheck/build；打包 Edge 真正复验另列后续任务|
|风险/回滚|其他客户端存在同类调用形态，须后续逐项验证，不能在本项跨模块顺手修改。若无效，可撤回这一行调用调整，历史数据不变。|

这是实际浏览器失败暴露的产品缺陷修复，不更改已冻结架构、数据模型、Schema 或 API，因此无需冻结基线 CR。旧固定候选不可追写，修复需进入新候选后才能重新宣称包内 Edge 通过。

## 验证结果

交接 `#get` 改为先取局部 `fetcher` 再调用，保持原参数、响应解析、权限与异常映射不变。新增 native-like 回归测试在接收对象上下文时抛 `Illegal invocation`，直接覆盖原 mock 的遗漏。定向 28/28、前端全量 1868/1868、`vue-tsc`/`tsc` 与 Vite 生产构建通过。未更改后端、Schema、迁移或冻结 API；本项不把源代码构建成功宣称为旧包 Edge PASS。

Changed：交接读取调用上下文与回归测试。Files：`handoverReadClient.ts`、`handoverReadClient.spec.ts`、本记录。Migration/API/权限：无。Tests：定向 28、前端全量 1868、typecheck/build PASS。Result：`HND_01_A05_A08_SOURCE_FIX_PASS / PACKAGED_RETEST_PENDING`。Known Issues：旧候选仍含缺陷；其他模块同类调用形态须各自实际验证。Next：新固定候选/真实 Edge 复验，正式 Pilot 仍 NOT_READY。
