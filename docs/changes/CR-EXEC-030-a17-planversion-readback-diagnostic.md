# CR-EXEC-030：A17 PlanVersion 固定版本回读诊断

- 日期：2026-10-29
- 状态：诊断完成，临时 wrapper 已从最终验收 Harness 移除
- 触发证据：托管 Windows 2025 run 40833168346 中基础完整测试/构建、A17 候选重建、PG18/pgvector 生命周期、D 盘临时路径守门均通过；PlanVersion Create HTTP 返回 201。调整 CR-EXEC-029 后，浏览器仍停留在 /versions/new，页面显示“草稿已创建；固定版本读回暂不可用”，因此不能判定为单纯路由等待竞态。失败日志中的最近 API 响应仅显示 Create 201，未包含预期固定 GET 200。
- 问题：需要区分读请求未发出/浏览器拦截、读 API 返回错误、或响应合同解析失败。当前没有足够证据判定产品 Owner/API 有缺陷。
- 范围：仅 A17 一次性浏览器验收器的网络诊断输出与结果记录；首步不改产品、API、Schema、权限、许可或既有验收条件。
- 方案：在 Edge DevTools Protocol 中记录只含 HTTP 方法、脱敏 API 路径、状态码及失败原因的请求生命周期；不记录请求/响应正文、Cookie、CSRF、密码、客户数据或 Secret。hosted Windows 完整重跑。若定位为产品行为缺陷，另建独立 CR，先记录影响、兼容、回滚和验证，再实施。
- 风险：诊断本身需再次构建大型临时候选；所有文件与运行均限定于 GitHub hosted Windows runner 的本轮 D 盘 runner temp。
- 回滚：移除新增诊断字段/事件监听；不触及产品包。
- 验证：检查请求是否发出、实际固定 GET 状态与浏览器加载失败原因；若返回成功则核对严格读响应合同、UUID详情路由、后续Validate=0、送审和PG状态/清理；所有日志仅保留非敏感元数据并通过现有 artifact 边界。
- 状态边界：A27 仍 IN_PROGRESS，Pilot/Gate/Release 不变。不得因 Create=201 推断固定 GET、Validate、Review 或数据库验收通过。

## 诊断结果（2026-10-29）

- run 40835305470 的 A17 Edge 运行没有发出固定 GET 请求，页面进入暂不可用分支。
- run 40837248488 的只用于诊断的浏览器 fetch wrapper 绑定 window 后，固定 GET 随后两次返回 200，应用完成 CreateView 固定回读并自动跳到 UUID 详情路由。该次 Harness 仅因仍要求旧 CreateView 成功提示而失败。
- 根因：PlanVersionReadClient.get 将自由原生 fetch 保存后通过实例成员调用，把 this 绑定到 Client 实例，导致浏览器原生 fetch 在发出请求前抛错；异常被映射为 PLAN_VERSION_READ_UNAVAILABLE。相同调用路径影响固定列表与详情 GET。产品/API合同本身保持不变。
- 修复范围已单独由 CR-EXEC-031 预先登记；本 CR 的诊断 wrapper 会在产品修复并得到对照验证后移除。

## 诊断器清理与最终对照（2026-10-29）

- 最终验收 run 40841364426 已移除窗口级 fetch wrapper，仅保留不含正文/凭据的 Network 方法、脱敏路径、状态码与加载失败诊断。
- 产品修复 CR-EXEC-031 在无 wrapper 条件下通过同一 A17 业务链；临时诊断代码不进入最终验证构建。
