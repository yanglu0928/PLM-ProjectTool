# A06-P05-P06-P09-P05 浏览器闭环前置与覆盖缺口核查

- 日期：2026-10-26
- 原WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P05`
- 结果：`PRECHECK_PASS_WITH_RECORDED_BASELINE_GAP`

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P05（前置核查）
输入基线：冻结API-04 PLAN_VERSION_CREATE/GET/VALIDATE/SUBMIT_REVIEW及DM-05 Requirement/WBS固定引用/覆盖；P09-P01～P09-P04页面；CR-PLAN-010
前置任务：Plan身份Edge/PG合成用户Harness、PlanVersion Create/Read/Validate/Review Owner及Windows显式生产组合、P09-P02 Create、P09-P03 Validate、P09-P04 SubmitReview均完成
涉及模块：Win11一次性Edge与本地Uvicorn/PG harness；PlanVersion创建/读回/Validate/送审/Review导航；仅合成Project/账户/来源
涉及实体：Approved Outline及Requirement固定版本、多个WBS任务、ValidationReport、Review/Round回执
涉及API：既有冻结Plan、PlanVersion、Project Member、Requirement Read、Review Read/Command；无新增API或Schema
涉及权限：合成项目负责人登录/管理；合成活动客户成员评审；API仍验证Session/CSRF/Project/License及来源
验收标准：只在固定来源/需求映射满足前提后执行真实Edge→本地HTTP→真实PG闭环；Create→固定ID读取→用户显式Validate→展示覆盖结果→PM选择活动客户评审人→显式确认SubmitReview→IN_REVIEW/Review detail；核对SQL Create/Validate/Audit/Receipt/Review/Round/PlanVersion状态、越项目/非PM拒绝、浏览器Network trace/异常、D盘临时资源清理；送审不得称为批准
风险：当前P09-P02 Create UI固定提交空requirement_refs且无exclusion输入；Validator对批准Outline里任何未映射Requirement阻断`REQUIREMENT_UNCOVERED`，Review Readiness又会在事务内复查。若只用零Requirement fixture做浏览器PASS，会掩盖真实产品不可走通的缺陷，故先修复输入再做E2E。
```

## 发现及计划调整

- `OutlineVersionDetail`含固定 `requirement_refs`；当前候选读取仅显示Outline/Section/StructuredSpec，不消费需求集。Create页面硬编码 `requirement_refs: []`。
- 后端Coverage以现时Approved来源Requirement全集为分母；任一未映射且未有正式SourceDecision排除/延期的项会失败。现有Create页面不支持SourceDecision，也不应由AI自动造此业务事实。
- 已创建 `docs/changes/CR-PLAN-010-planversion-requirement-coverage-workbench.md`，按持续授权选择方案B：多WBS根任务+用户逐项固定Requirement映射，不改冻结合同/API/Schema。
- 原P09-P05拆分：`P09-P05-A01`先完成需求映射Create UI，`P09-P05-A02`再完成完整Win11 Edge/PG闭环；不伪造零需求E2E替代结果。

## 后续约束

- 编码前先同步本核查与CR；A01保持无AI自动业务映射、无客户资料外发、无数据库变更。
- 新浏览器Profile、PG数据、日志、截图、wheel等临时输出放在`D:\PLM-Test-Temp`或仓库专属验证目录；不将系统Temp作为新输出目标。
