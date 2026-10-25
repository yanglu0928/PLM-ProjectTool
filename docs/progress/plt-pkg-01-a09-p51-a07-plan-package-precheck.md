# PLT-PKG-01-A09-P51-A07：Plan 候选包内身份验收前置

日期：2026-10-25；状态：`PASS_SCOPE_LIMITED_IDENTITY_ONLY`（Windows 11 当前非发行候选；合成数据）。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `PLT-PKG-01-A09-P51-A07`|
|输入基线|`CR-EXEC-002`；固定P51候选SHA `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；冻结DM-05/API-03 Plan身份合同；P51-A02已验证stage|
|前置任务|P51-A03包内HTTPS/PG；A04 Survey Review；A05 Prototype；A06 Solution Outline身份创建/读取均已完成限定范围验收|
|涉及模块|仅新增一次性候选包Edge验收器；不修改产品Owner/API/ORM/Migration/权限|
|涉及实体/API|合成Project内Plan身份；只走候选包的 `/api/v1/projects/{project}/plans` 创建与详情读取|
|涉及权限|合成ProjectManager/ImplementationMember；当前会话通过Edge登录，不能读取其他Project；不生成PlanVersion、WBS、Review决定或Output|
|验收标准|当前固定候选的Windows11 Edge经候选包HTTPS创建并读取Plan；PG核对ACTIVE身份、项目/创建者、批准指针为空、唯一Audit与同事务幂等回执；候选SHA不变，临时PG/Vault/服务/Profile/layout清理|
|风险与回滚|Plan身份不等于计划版本、WBS、客户批准或交付；只写入一次性临时数据库，可随本轮销毁；不触碰现有正式安装、数据库、SCM或客户资料|

## 路由核对与边界

- `production_login.py` 在显式Windows `include_secret_write` 组合下创建 `plan_create_router`；前端已有 `/projects/:projectId/plans/new` 和Plan详情页。页面明确只建立身份，不生成版本、WBS、Review或交付文件，和本WBS范围一致。
- Plan身份创建不依赖 Approved Solution 来源，避免重复A06发现的缺少Approved Section fixture阻塞；但也不证明PlanVersion、Solution固定来源、WBS依赖图或Output可用。
- 编码前检查结论：基线、前置、模块、实体/API、权限、验收、风险均已核对；不改冻结合同，无需CR。只新增 `validation/plt-pkg-01-a09-p51-a07-plan-packaged/` 一次性验收器。

## 最终验收结果

- 固定候选 SHA-256 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455` 未改变；使用包内 Windows Python/Caddy/PostgreSQL 18.6 与本机 Edge，测试前后核验候选哈希，临时服务、Vault目标、Edge Profile 和隔离布局清理通过。
- Edge 经候选包 HTTPS 创建并读取 Plan 身份：创建 HTTP 201、读取 HTTP 200；PG 核对 `ACTIVE`、名称/创建者/项目匹配、批准版本指针为空，且恰有一条 `PLAN_CREATED` Audit 和一条 `V1_PLAN_CREATE` 完成收据。没有创建 PlanVersion、WBS、Review 决定或 Output。
- P51 上游包内 Handover、Survey、Prototype 回归链和 A06 Solution Outline 身份探针均通过。其合成上游批准仅为测试夹具，不构成客户事实或业务批准。
- 验证：全包 Edge/HTTPS/PG smoke 退出码 0；`tools/tests/test_smoke_current_app_packaged_https.py` 与 `tools/tests/test_smoke_packaged_platform_write_https.py` 定向回归 6/6 通过；A05/A06/A07 Python 编译检查及 Edge runner Node 语法检查通过。
- 结果边界：仅证明本候选包中 Plan 身份创建/读取切片；`release_eligible=false`、`legal_clearance=false`。PlanVersion 来源资格、WBS/依赖、Output、正式信任/安装、Pilot/Gate/正式发行和其他平台均未由此关闭。

## 文件与结果

- 新增 `validation/plt-pkg-01-a09-p51-a07-plan-packaged/verify.py` 与 `run-edge-browser.mjs`，只用于一次性隔离验收；无产品代码、API、ORM、Migration或依赖变化。
- 首轮及回归执行结束后确认未遗留 A06/A07 临时目录或 Edge 进程；固定候选哈希复核一致。
- Result：`PASS_SCOPE_LIMITED_IDENTITY_ONLY`。下一项建议先对候选包 Plan 身份创建/读取的跨项目与角色权限边界做编码前核查；不把该边界测试与 PlanVersion Owner 缺口混为一项。
