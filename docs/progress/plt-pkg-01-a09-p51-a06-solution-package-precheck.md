# PLT-PKG-01-A09-P51-A06：Solution 当前候选包内验收前置

日期：2026-10-25；状态：`PASS_SCOPE_LIMITED_IDENTITY_ONLY`（Windows 11 当前非发行候选；合成数据）。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `PLT-PKG-01-A09-P51-A06`|
|输入基线|CR-EXEC-002；固定P51当前候选SHA `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；冻结Solution DM-05/API-04及PILOT-CHAIN-A02路线核查|
|前置任务|P51-A02文件落地、A03包内PG/HTTPS、A04 Survey Review、A05 Prototype Edge/HTTPS/PG均通过；Solution Outline源码级Review链已有历史证据，但尚无当前固定候选的对应包内证据|
|涉及模块|仅新增/适配一次性候选验证编排，在当前包内HTTPS/PG环境验证一个Solution Owner切片；不改产品Owner/API/ORM/Migration/权限|
|候选切片|依该package fixture实际状态，固定为当前候选包内 Project Solution Outline 身份创建/读取：Edge经包内HTTPS创建合成Outline，数据库核对ACTIVE身份、Audit和同事务幂等回执；不创建版本、不送Review|
|涉及权限|只使用临时合成Project与测试账户；实际API请求通过当前包内HTTPS；严禁自动作任何真实Review决定，不将测试Approved或AI建议描述为客户事实|
|验收标准|预先固定候选SHA；实际Edge连接包内Caddy HTTPS；数据库核对Outline身份/版本/状态/固定来源/Trace或Review关联及Audit/幂等结果；测试前后候选同SHA，临时Vault/PG/服务/浏览器/目录均清理|
|风险与回滚|Solution UI依赖完整Approved输入与正式来源证明；不得用伪造引用或绕过校验满足下游Plan。新增验证脚本及本轮隔离资源可弃用；候选、正式数据库、服务和客户事实不变|

## 核对结果与执行前置（2026-10-25）

- 当前源码 `production_login.py` 明确将 Outline 只读路由挂在显式 `include_secret_read` Windows 组合，将 Outline身份/版本创建、验证、送审路由挂在显式 `include_secret_write` 组合；候选包 smoke 启用该隔离写组合。前端现有 `/projects/:projectId/solution-outlines/:outlineId/versions/new` 和版本详情/Review页面，送审Owner已由 `OutlineReviewSubmitPanel` 实现。版本详情暂没有单独 Validate 按钮，因此此切片不宣称或测试前端 Validate 操作；送审服务仍会服务端重验来源和资格。
- 运行方案核对发现既有 `validation/sol-03-a06-p03-a05-p03-a05-p02-full-source-pg/verify.py::_approved_section_v2` 并非从空白项目造出前置，而是依赖同一项目中已有Approved Section/Requirement。当前P51包内fixture没有可供其升级的Approved Section，临时库清理后也不存在客户级输入。本轮遵照原预案的失败关闭回退，不创建/批准客户事实、不绕过固定来源，将本WBS缩小为当前候选可独立验收的Solution Outline身份Owner。
- 验收由新Edge runner通过当前固定候选包的HTTPS源站创建并读取合成Outline；数据库核对`ACTIVE`身份、未批准指针、唯一 `SOL_OUTLINE_CREATED` Audit 及 `V1_SOL_OUTLINE_CREATE` 完成回执。候选SHA与临时资源清理沿用P51-A05 runner。版本/Trace/Review未验，继续留作后续链路，不以本项推断通过。
- 编码前检查结论：输入基线、前置任务、模块、实体、API、权限与验收标准已确定；无产品代码/ORM/Migration/公开API修改，无需CR。隔离验收器只新增于 `validation/plt-pkg-01-a09-p51-a06-solution-packaged/`，不接触真实客户资料、正式数据库、License私钥或生产安装。

## 最终验收结果

- 固定候选 SHA-256 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455` 未改变；复用P51-A02已验证stage和A05隔离布局方式，包内Windows Python/Caddy/PG18 smoke完成，临时服务、Vault目标及隔离目录全部清理。
- Windows 11 Edge通过候选包内HTTPS创建并读取Solution Outline身份，HTTP创建201、读取200；PG核对`ACTIVE`、创建者/项目归属正确、批准版本指针为空、恰有1条`SOL_OUTLINE_CREATED` Audit及1条`V1_SOL_OUTLINE_CREATE`完成幂等收据。没有创建Solution版本或评审，不存在人为批准。
- 上游Handover/Survey/Prototype包内回归链全部通过；固定候选整体标识仍`release_eligible=false`、`legal_clearance=false`。端到端纵向链、Approved Section/Requirement输入、Solution版本/Trace/Review、PlanVersion/WBS/Output、正式信任、Pilot/Gate、多平台及发行仍未证明。
- 验收适配记录：首轮命名空间回调未触发A06探针，加入强断言后修正；版本/Review fixture依赖的Source-level Approved Section helper假设既有SQL fixture，在当前空Solution包内fixture不成立，因此按预案改测Outline身份Owner，不制造批准；包运行使用`localhost` HTTPS及具备内存态会话的SPA，Edge runner相应允许合成证书并保持SPA路由；创建成功会立即跳转详情，断言据此改为详情页及回执/数据库核对。均为测试装配调整，无产品缺陷证据、无产品/API/Schema/Migration修改。
- 验证：P51全包Edge/HTTPS/PG smoke退出码0；`tools/tests/test_smoke_current_app_packaged_https.py` 与 `tools/tests/test_smoke_packaged_platform_write_https.py` 定向回归6/6通过；A06 Python `py_compile`、Edge `node --check`通过。

## 文件与结果

- 新增 `validation/plt-pkg-01-a09-p51-a06-solution-packaged/verify.py` 和 `run-edge-browser.mjs`。仅为一次性隔离验收器，无产品代码、Migration或API Contract变化。
- Result：`PASS_SCOPE_LIMITED_IDENTITY_ONLY`。Known issues：Outline版本的Approved来源fixture尚未在当前候选包场景闭合；仅本项未验，不能误写为产品Bug，也不能由身份读取PASS推断版本或评审PASS。
- Plan身份包内切片已在P51-A07完成；Plan跨项目读取隔离在P51-A08完成。缺失的Approved Solution业务来源仍未闭合，不得复用伪造客户批准；后续包验证已转至P51-A09 API进程重启持久性。

## 路线依据

PILOT-CHAIN-A02已明确：Solution结构化专项及Outline Review有分项源码/PG/Edge证据；PlanVersion/WBS固定Approved来源Owner尚未闭合；OutputArtifact正式Owner仍缺。P51-A05～A08已补齐固定候选Prototype、Outline身份、Plan身份及跨项目读取隔离的包内分项证据；这些均不代替完整批准来源链。即使后续包验证通过，也不解除Plan真实Approved集合、Output Owner、正式信任/安装、Gate 3和Pilot UAT阻塞。

## 执行边界

编码前先核对当前候选中Solution路由/页面/组合注册与现有 `validation/sol-*` 测试夹具映射；必须选择单一具体Solution Owner问题并补齐TraceLink。任何需要不存在的客户批准、目标服务账户Vault、公钥或外发材料才能成立的验收停止该支路并记为阻塞，转到不依赖该前置的包内安全/重启检查；不得提交全链通过或Pilot就绪结论。
