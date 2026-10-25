# A06-P05-P06-P06 PlanVersion 写Client / SessionClient桥接

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P06`
- 结果：`PASS_SCOPE_LIMITED`
- 编码前依据：`docs/progress/plan-02-a04-p04-a04-p03-p04-s03-p03-a06-p05-p06-p06-version-write-client-precheck.md`

## 实现

- SessionClient增加PlanVersion create（8 MiB上限）、bodyless Validate及原子SubmitReview精确同源路由，沿用既有CSRF/idempotency/single-attempt timeout/401清Session逻辑；调用层超时不得隐式换key重试。
- 新增`PlanVersionWriteClient`：校验精确快照字段与PM/实施成员权限、固定版本创建响应及Location、完整Validate报告/覆盖计数、SubmitReview只允许PM并固定`PLAN_VERSION_ALL_V1`与`due_at/submission_note=null`；送审结果仅为`IN_REVIEW`，固定Reviewer排序，验证强ETag与响应字段。
- 本项没有增加页面、读取Client、API/Schema或数据库内容，保持版本collection接口缺失这一既有约束。

## 验证

- 定向SessionClient与PlanVersion写Client：`176 passed`。
- 前端全量：`193 files / 2050 passed`（Vitest `--maxWorkers=2`）；`pnpm typecheck`通过；`pnpm exec vite build`通过。
- 构建提示主JS chunk超过500 kB阈值；未在本WBS扩展拆包范围。

## 偏差 / 限制

- 首次将全量测试与生产构建并行运行时，Node worker因环境内存竞争OOM；未作为代码失败结论。改为单项串行并限制Vitest两个worker后，全量通过。
- 测试仅验证前端合同/SessionClient；未运行Windows Edge、已装配的后端Write API或真实信任。PlanVersion页面、历史列表、完整创建来源选择与输出能力仍未完成；Gate/Pilot/Release状态不变。

## 下一项

`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P07`：固定PlanVersion工作页前置核查与UI单项切片规划，覆盖不可变快照、可见来源选择、Validate门控、原子送审及已知历史列表缺口。
