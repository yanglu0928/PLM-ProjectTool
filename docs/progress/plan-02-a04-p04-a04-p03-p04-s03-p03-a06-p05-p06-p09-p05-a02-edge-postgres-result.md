# A06-P05-P06-P09-P05-A02 Windows 11 Edge/PG 闭环结果

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P05-A02`
- 结果：`PASS_SCOPE_LIMITED`
- 变更记录：`CR-PLAN-011`、`CR-PLAN-012`；原编码前检查 `PRECHECK_PASS_WITH_HARNESS_ADAPTATION`

## 闭环结果

- 新增一次性隔离Harness：Windows 11 实际 Edge、Vue构建产物、FastAPI/Uvicorn、PostgreSQL 18.6真实HTTP/数据库；账户、License、批准Outline/Section/Requirement固定来源和评审人为合成数据。Session通过真实登录与CSRF建立；没有客户数据外发。
- Edge链路：PM登录→已批准Outline固定版本→读取固定Requirement正文→用户显式把需求映射到两个WBS→POST Create→按固定ID读取快照→Validate通过且未覆盖需求为0→选择合成活动客户评审人并确认原子送审→Review页由合成客户评审人登录读取。
- PostgreSQL独立读回：PlanVersion状态=`IN_REVIEW`，2个WBS/2条需求引用/1份Validation结果；Review/Round均=`IN_REVIEW`；1个Reviewer Assignment、0个Decision、1个STARTED事件、2条Review/Round Audit、1条完成的`V1_PLAN_VERSION_SUBMIT_REVIEW`收据。没有替合成或真实评审人作决定。
- 用于一次性测试的 Edge Profile、PG数据和输出均在 `D:\PLM-Test-Temp`；run脚本只回收本轮拥有的隔离环境。截图作为本机临时验证产物，不进入仓库。

## 编码期间发现并记录的差异

- `CR-PLAN-011`：合法 `PROJECT_MANAGER` 送审因授权矩阵缺少冻结操作 `PLAN_VERSION_SUBMIT_REVIEW` 被安全隐藏为404。补齐仅负责人可写的既定策略并扩展矩阵测试，没有扩大权限。
- `CR-PLAN-012`：Review GET返回成功，但严格前端白名单不认识冻结`PLN-02`/`PLAN_VERSION_ALL_V1`。补齐只读类型/策略解析与页面标签，显示服务端固定Version ID；Review GET没有PlanId，故不臆造固定Plan详情链接。没有修改Review决定路径。
- 验收Harness原先尝试logout；本次只读/登录应用组合未装载logout Router，返回405。改为打开真实登录页并以合成评审人重新登录；未为测试放开或新增生产logout端点。
- 初次完整后端回归的128 MiB snapshot测试使用默认C盘Temp，因磁盘空间不足失败。定向重跑通过，将本轮完整后端测试Temp设为D盘后全量通过。初次默认并发前端全量测试发生Node分配OOM，改为单工作线程串行后全量通过。环境问题均保留，不作为功能缺陷或隐去的失败。

## Files / API / Migration

- 后端：`project/application/authorization.py`及授权矩阵测试。
- 前端：`ProjectReviewClient`严格主体/策略配对及Review页面计划版本显示、相邻spec。
- 验证：`validation/plan-version-edge-postgres/`独立Harness、Node Edge runner及SQL读回。
- 记录：本结果及`CR-PLAN-011/012`，并更新`STATUS.md`和`CHANGELOG.md`。
- API合同无变化；没有ORM、Schema、Migration、依赖或客户数据变更。

## 验证

- 定向后端授权/送审/HTTP/Windows组合：28 passed，868子断言通过。
- 后端全量：4190 passed、3 skipped、6224子断言通过（`TEMP`/`TMP`指向D盘）。
- 前端Review定向：16 passed；前端全量：199 files / 2068 tests passed；typecheck通过；Vite生产构建通过。保留既有主bundle超过500 kB提示。
- Windows 11 Edge→HTTP→PG：浏览器闭环退出0；PG断言严格核对Review/Round/Assignment/Audit/Receipt且决定数为0。
- `git diff --check`及Secret检查待提交前最终执行。

## 限制与后续

- 本项是合成身份/License/来源的Win11业务闭环，不代表真实客户来源批准/确认、正式服务账户/发行信任、Pilot、Gate或正式Release；Windows Server 2025与Debian 13未在本项验证，Debian实机仍按用户指令跳过。
- Review GET冻结投影没有PlanId，PlanVersion Review页显示固定版本身份但暂不链接回Plan详情；不影响评审读取或决定权限。
- `C:\Users\17231\AppData\Local\Temp`未能清理：本轮删除动作被Windows安全策略拒绝，未尝试绕过；新的测试临时输出已改用D盘。建议用户使用Windows“设置→系统→存储→临时文件”审阅清单后清理，避免选择下载项。
- 下一项：`PLT-PKG-01-A09-P51-A17`，在当前Win11非发行候选中集成本轮PlanVersion创建/校验/Review前端，并复验包内Edge/HTTPS/PG业务链；仍为受控内部候选，不得称正式发行。
