# A06-P05-P06-P09-P05-A02 Windows 11 Edge/PG闭环编码前检查

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P05-A02`
- 结果：`PRECHECK_PASS_WITH_HARNESS_ADAPTATION`
- 变更依据：`CR-PLAN-010`、`CR-EXEC-002`

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3未通过
当前WBS：PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P05-A02
输入基线：冻结DM-05/API-04 PlanVersion Create/GET/Validate/SubmitReview；CR-PLAN-010需求映射；P09-P01～P09-P04 UI/Client；P09-P05-A01结果
前置任务：PlanVersion真实PG Create/GET、Validate Owner、原子送审HTTP/事务已有Win11 PG18证据；P09页面全齐；A01已完成Requirement映射并全前端验收通过
涉及模块：一次性Win11 Edge/Uvicorn/PG18测试Harness及浏览器回归；必要时仅调整隔离验证脚本，不修改产品后端/合同
涉及实体：合成Project/PM/客户评审人、批准Outline/Section/Requirement固定版本、PlanVersion/WBS、ValidationReport、Review/Round/Plan状态与Audit/Receipt
涉及API：真实本地Session/Project/Outline/Requirement/PlanVersion HTTP组合；没有新增产品API
涉及权限：真实Session登录和项目角色数据；测试License/发行信任/来源审批/验证证明明确为合成替身，客户评审人为合成账户
验收标准：Windows 11 Edge实际交互登录→选择Approved Outline固定版本→指定版本Requirement正文读取→用户显式映射到多WBS→POST Create→固定ID GET逐字段读回→显式Validate并报告需求覆盖→PM选择合成活动客户评审人并确认原子送审→IN_REVIEW/Review detail；PG核对WBS映射、Validation/Audit/Receipt/Review/Round/Plan状态；CSRF/来源边界/重复点击或未知写回/异常状态检查；记录浏览器Network及截图；所有DB/Profile/log输出放D盘并回收仅本次拥有的资源
风险：现有Plan identity Edge Harness只覆盖Plan根身份，Node以os.tmpdir创建Edge Profile且未挂接PlanVersion/Outline/Requirement/Review路由；不得直接复用并宣称闭环。需要新增一次性PlanVersion Harness/runner并强制`PLM_BROWSER_TEMP_ROOT=D:\PLM-Test-Temp`。测试仅合成来源/身份；不能称真实客户审批、正式信任或Pilot
```

## Harness差距与实施边界

- 已有`validation/plan-01-a04-p05-a03-edge-browser`具备Win11 Edge/CDP、实际登录、隔离PG/Uvicorn及权限/分页检查，可作结构参考，但没有PlanVersion完整页面或批准Outline需求固定版本；其Edge Profile当前用系统`tmpdir()`，禁止原样运行。
- P09-P02独立验证脚本提供隔离PG迁移和PlanVersion HTTP/固定读取，不使用真实浏览器；P03 Owner PG验证具备Create/Validate服务组合；P06-P04证据已有原子送审数据库/HTTP事务。
- A02仅新增隔离验证Harness/浏览器runner/结果证据，不扩展产品Scope。优先接真实固定来源只读Owner与PlanVersion写/验证/送审生产组合；账户/License/信任与批准来源如由合成fixture代替必须逐项披露。
- 所有PG data、Edge profile、日志、截图放在`D:\PLM-Test-Temp`；仅删除脚本在本次创建且路径校验通过的临时目录；系统Temp现有数据保持未动（Windows拒绝了递归清理尝试）。
