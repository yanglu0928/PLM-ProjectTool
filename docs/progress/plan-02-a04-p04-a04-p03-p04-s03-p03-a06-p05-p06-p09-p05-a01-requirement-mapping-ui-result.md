# A06-P05-P06-P09-P05-A01 PlanVersion需求映射UI实施结果

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P05-A01`
- 结果：`PASS_SCOPE_LIMITED`
- CR：`CR-PLAN-010`；编码前检查已先提交并推送

## 变更

- Approved Solution候选加载现在逐条读取Outline固定RequirementRef对应的当前Requirement与指定RequirementVersion；核验Project/根ID/当前批准版本指针/APPROVED状态，任一缺失或不一致即失败关闭。
- PlanVersion创建表单支持1～100个WBS根任务；用户可将每个固定需求分配给一项或多项任务。需求未完整覆盖、任务字段缺失、WBS代码重复/不合法或日期不成对时，禁止预览/创建。
- 创建前刷新若需求固定身份集合变化则停止；幂等待定操作继续保持原完整请求体与原Key。创建后读回逐项校验所有WBS固定字段。
- UI显示固定需求编码/版本/标题或正文，提供需求详情链接；明确不自动做业务映射，不代造排除/延期结论。

## Files / Migration / API

- Files：`apps/frontend/src/modules/plan/api/planVersionApprovedSolutions.ts`、对应spec、`ProjectPlanVersionCreateView.vue`及对应spec；新增本结果记录；更新`STATUS.md`、`CHANGELOG.md`。
- Migration：无。
- API：无变化；只消费既有Requirement根/版本只读接口与冻结PlanVersion Create。
- 后端Owner/Validate/Review readiness保持权威并重新验证覆盖。

## 验收

- 定向：2个文件/6项测试通过，覆盖固定Requirement版本读取、批准指针变化失败关闭、提交映射内容，以及未映射需求阻止预览。
- 全量：199 files / 2066 tests通过。
- `npm run build`：Vue/TypeScript类型检查通过，Vite生产构建成功；仍有既有主Chunk >500 kB告警。
- `git diff --check`通过。构建临时目录设置为`D:\PLM-Test-Temp`。
- 未运行本片Edge/PG E2E；这将是A02验收。未验证正式账户/License信任、客户批准、Gate、Pilot或Release。

## 限制与下一项

- 固定需求来自所选Approved OutlineVersion的`requirement_refs`；本表单不提供SourceDecision排除/延期输入。如当前范围需要该正式决定，必须在上游方案中形成可验证批准来源后再创建，不能在本UI绕开。
- 下一项：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P05-A02`，使用D盘隔离资源完成Windows 11 Edge、HTTP和PostgreSQL端到端Create→固定读取→Validate→PM送审→Review页闭环，并清晰标识合成授权/来源替身。
