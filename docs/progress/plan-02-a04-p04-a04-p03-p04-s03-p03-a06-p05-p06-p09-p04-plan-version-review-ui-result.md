# A06-P05-P06-P09-P04 PlanVersion 原子送审页面结果

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P04`
- 结果：`PASS_SCOPE_LIMITED`

## 实施

- 固定PlanVersion详情仅为ProjectManager在DRAFT且没有Review引用时显示送审入口；新增独立送审页面。
- 完整读取项目成员历史后，仅向负责人展示`ACTIVE`的CUSTOMER_MANAGER/CUSTOMER_MEMBER，成员分页不完整、cursor重复、重复member id时失败关闭。
- 送审需明确选择客户评审人和人工确认，严格限制1～32人；页面通过PlanVersionWriteClient提交冻结`PLAN_VERSION_ALL_V1`原子命令。
- 提交前将固定reviewer集合、主体/版本及幂等Key写入sessionStorage。结果不确定时仅允许原reviewer集合与原操作号人工确认重试；确定拒绝需重新加载成员资格；成功严格校验回执的Project/Plan/Version/提交人并显示IN_REVIEW Review/Round，绝不显示批准。
- 复用既有Review detail路由，不新增API/Schema/Migration或后端写组合。

## 验证

- 定向前端：送审页和PlanVersion详情2 files / 5 tests通过；覆盖客户评审角色过滤、显式确认、同Key重试、实施成员拒绝、重复分页失败关闭。
- 前端全量Vitest：199 files / 2064 tests通过；typecheck和生产构建通过。构建显示既有主chunk >500KB提示。
- 后端定向：SubmitReview API/Service/Readiness/Terminal/Windows composition `27 passed`。
- 未新跑PostgreSQL HTTP/Edge；复用本日既有P06-P04隔离Win11/PG18真实SubmitReview HTTP、Review/Round/Plan结果/Audit/Receipt事务、同Key重放与Audit回滚证据，详见`plan-02-a04-p04-a04-p03-p04-s03-p03-a06-p05-p06-p04-submit-review-http.md`。其中Session/License/PM授权/Reviewer/批准来源Evaluator为合成替身，不代表真实客户送审、生产信任或UAT。
- `git diff --check`和Secret扫描通过；未读写客户材料。

## 限制与后续

- 当前为页面与现有显式Windows写组合的验证测试；未执行Windows Edge到真实PG的浏览器业务链、正式信任/真实客户评审；Server 2025、Debian 13、Gate/Pilot/正式Release仍未通过。
- 下一项 `PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P05`：先核查现有Windows 11运行/登录/PG/Edge harness，将“创建固定草稿→读回→显式Validate→PM选择客户评审人→原子送审→评审页”作为一次性合成浏览器闭环；保持真实批准只由Review决定。
