# A06-P05-P06-P09-P01 PlanVersion 历史与固定快照页面结果

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P01`
- 结果：`PASS_SCOPE_LIMITED`

## 实施

- 增加 PlanVersion 历史页和固定快照详情页，支持分页、刷新、只读快照浏览、权限/强制改密状态、错误/空状态及路由变化期间屏蔽旧响应。
- 增加严格校验冻结列表与固定读取响应的前端 Client，并从计划身份页链接至历史页。
- 将现有固定版本 Read Owner/router 加入显式 Windows `include_secret_read` 组合；登录-only/默认应用仍不装配该读取器。
- 不改变冻结 API Contract、ORM、数据库 Schema 或 Migration。Validate、SubmitReview 和草稿创建均不属于本项页面操作。

## 验证

- 前端：`pnpm typecheck` PASS；全量 Vitest `195 files / 2053 tests PASS`；`pnpm build` PASS。构建存在既有主 chunk >500KB 警告，不影响本项构建结果。
- 后端：完整 pytest `4190 passed / 3 skipped / 6219 subtests passed`。
- Windows 11 + 隔离 PostgreSQL 18：migration upgrade/check、真实 SQL 固定版本读取及 HTTP 返回快照通过；跨计划固定版本读取返回 404。Session、License 与 Project 授权为合成替身，不代表正式信任/UAT。
- 后端 wheel 在 D 盘临时输出构建成功，并确认包含 `production_login.py` 与 Windows PlanVersion composition 模块。
- 后续P09-P02编码前复核发现PlanVersion `calendar_ref` 是冻结的受限代码字符串（非UUID）；前端固定快照校验已按后端输入约束改为验证代码格式，并新增回归用例。该修正不改变API/Schema。
- 生产只读启动合同：显式只读模式固定版本 GET 未登录返回 401；login-only 未装配该路由。动态 GET 路由对误用 POST 的 `:validate` 路径产生 405（仅方法未允许，不存在 Validate 写处理器）；login-only 仍返回 404。记录为框架对路径匹配的正常方法响应，不改变写权限边界。
- Secret/客户数据：无客户数据进入验证；提交前仅允许本项源代码、测试与文档进入暂存。

## 限制与后续

- 本次固定快照中结构化快照集合通过 JSON 只读展示；来源当前资格、业务验收、批准及交付状态仍须使用各自 Owner/流程判断。
- 下一 WBS `PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P02`：构建完整不可变草稿创建表单，选择已批准 Solution 固定版本，录入 WBS 根任务及准入/验收条件，预览后创建并按固定版本 ID 读回。保持 Validate/Review 独立。
- 不代表 Gate、Pilot 或正式 Release 通过。
