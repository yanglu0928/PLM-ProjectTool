# PLT-PKG-01-A09-P51-A08：Plan 当前候选包跨项目读取隔离前置

日期：2026-10-25；状态：`PASS_SCOPE_LIMITED_CROSS_PROJECT_READ`（Windows 11 当前非发行候选；合成数据）。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `PLT-PKG-01-A09-P51-A08`|
|输入基线|`CR-EXEC-002`；固定P51候选SHA `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；冻结DM-05/API-03 Plan读取合同|
|前置任务|P51-A02文件落地、A03包内PG/HTTPS、A04 Survey Review、A05 Prototype、A06 Outline身份、A07 Plan身份均在限定范围通过|
|涉及模块|一次性当前候选Edge/HTTPS/PG验收器；不改产品Owner/API/ORM/Migration/权限|
|唯一问题|登录用户读取自己可访问项目内已创建Plan后，以另一项目ID请求同一Plan ID；确认响应不枚举跨项目对象|
|涉及权限|仅一次性合成库、合成用户和随机不存在的项目UUID；不访问客户数据，不生成业务写入/Review决定|
|验收标准|同项目Plan GET为200；跨项目同Plan GET为404且响应不含Plan名称/ID；PG确认仍只有原Plan身份、Audit、创建幂等收据，候选SHA不变，临时资源全清理|
|风险与回滚|只新增验收脚本并扩展既有一次性Edge runner的可选负向探针；该探针关闭时A07命令行为不变。移除验证器即可回滚，不涉及产品与正式状态|

## 代码/合同核查

- `apps/backend/src/plm_assistant/modules/plan/api/read_plan.py` 使用冻结 `/api/v1/projects/{project_id}/plans/{plan_id}`，服务端统一映射未授权/不存在目标，且不回显Plan正文。
- `validation/plan-01-a03-p03-read-owner/verify.py` 已证明服务层对错项目返回 `RESOURCE_NOT_FOUND`；A08只补当前固定候选包内实际Edge/HTTPS证据，不重复宣称Owner实现。
- 此任务不触碰 PlanVersion 来源资格、创建/验证/送审或跨项目真实数据；没有冻结API变更，无需CR。
- 编码前检查结论：范围、前置、基线、验收及回滚明确，允许新增隔离验证代码。

## 最终验收结果

- 固定候选 SHA-256 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455` 未变。Windows 11 Edge登录同一合成成员；同项目读取Plan成功，改用随机且无成员关系的项目UUID读取同一Plan，HTTPS/API响应为404且不包含Plan UUID或名称。
- PG复核跨项目请求未增加或移动任何业务行；本项创建的合成Plan仍唯一，状态/名称/项目/创建者正确，只有一条 `PLAN_CREATED` Audit和一条 `V1_PLAN_CREATE` 完成收据。
- P51完整上游Handover/Survey/Prototype、A06 Outline身份、A07 Plan身份和A08边界探针均通过；包内登录/Session/无License保护路由拒绝、Caddy/Python/PG、48个临时Vault目标和候选SHA检查通过，API/Caddy/PG与本轮隔离布局清理完成。
- 初次使用系统Python 3.13运行单测时缺 `httpx`，未安装依赖；随后改用当前候选已随包交付的隔离依赖目录设置 `PYTHONPATH`，两个smoke单测模块6/6通过。A05-A08 Python AST与A07 Edge runner Node语法检查通过，`git diff --check`通过。
- 未验证PlanVersion/来源资格、完整纵向链、正式信任/安装、Pilot/Gate、其他平台或发行。候选仍 `release_eligible=false`、`legal_clearance=false`。

## 文件与偏差记录

- 新增 `validation/plt-pkg-01-a09-p51-a08-plan-cross-project-packaged/verify.py`；将A07 Edge runner扩展一个可选 foreign-project 参数，默认A07行为不变。没有产品/API/Schema/Migration/依赖变化。
- 首轮测试命令发现用于包内运行的临时Python在 `stage/payload/runtime` 而不是安装映射目录，修正为已核验stage自带解释器；本机测试依赖缺 `httpx` 时直接复用候选内隔离依赖路径完成6/6回归，没有下载或安装新依赖。
- Result：`PASS_SCOPE_LIMITED_CROSS_PROJECT_READ`。下一项进入候选包API进程重启后的Plan/Session持久性前置已记录在P51-A09。
