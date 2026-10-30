# CR-EXEC-029：等待 PlanVersion 创建后的固定详情路由

- 日期：2026-10-29
- 状态：已由 CR-EXEC-031 修复并经无诊断 wrapper 的 hosted 完整流程复验通过
- 来源与证据：GitHub hosted Windows 2025 run 40831017596 中基础/前端测试、候选构建、PG lifecycle、D-drive guard、Section/Requirement/Outline Review 均通过；Edge UI 已触发 PlanVersion 创建并展示“草稿版本已创建：”。随后脚本在 run-edge-browser.mjs 从 location.pathname 最末段读取版本 ID，得到非 UUID 并失败。前端 ProjectPlanVersionCreateView.vue 中 createdId.value 在 create API 返回后即设置，模板立即展示成功链接；固定版本 GET 回读在其后执行，再由 router.push 跳转详情。因此脚本只等待提示文字会早于固定读取/路由跳转。
- 问题：验收脚本把异步创建收据提示当成详情路由就绪，产生时序竞态；PlanVersion Create 已发生，固定版本 GET 与后续 Validate/Review 尚未验收。
- 方案比较：A. 从成功链接 href 读取 UUID；B. 等待成功提示与详情路由末段 UUID 同时成立后再读 ID。选择 B，继续沿页面真实 readback→router navigation 路径验收。
- 基线差异：仅改 A17 Edge 验收脚本的 waitFor 条件，不改 UI、API、产品状态机或验收要求。
- 影响与风险：不增加宽限来忽略错误；若 fixed readback 失败，前端不会完成 router.push，Harness 会在时限内失败而不误判。业务 Create 已发生在隔离 disposable PG，由整个 runner 执行后清理。
- 回滚：恢复仅检查成功提示的 waitFor；不影响产品功能。
- 验证计划：hosted Windows 2025 完整流程；确认先 Create 201，再 fixed detail GET 200，详情路由 UUID 正确；Validate coverage=0，SubmitReview 与 PG Version/WBS/Requirement/Validation/Audit/Receipt/Review/Round 均一致且 decisions=0；核对 Edge 退出、仅清本轮临时目录及 candidate hashes。A27 未通过前不标 PASS。
- 执行边界：仅 GitHub hosted runner 与合成数据；不在用户本机/C盘运行项目代码，不外发客户资料或 Secret。

## 实施结果（2026-10-29）

- 已在 `d9c27e3f74109a9d13b7933623f16376afdeadda` 将 Edge 等待条件改为成功回执与 UUID 详情路由并存；语法/D 盘路径守门及其他基础步骤通过。
- run 40833168346 证明 Create 返回 201，但页面报固定读回暂不可用，未进入详情。故原先“仅时序竞态”的推测被证据否定，A27不通过；按 CR-EXEC-030 采集请求生命周期诊断。

## 最终验收（2026-10-29）

- run 40841364426 在 hosted Windows Server 2025 完成 A17 包内 Edge/HTTPS/PG 完整旅程；路由等待改为依赖稳定详情页快照，不依赖瞬时创建提示。
- 结果见 docs/progress/plt-pkg-01-a09-p51-a27-planversion-cloud-result.md；A27为 PASS_LIMITED，未将托管服务器结果推断为 Windows 11 本机验收。
