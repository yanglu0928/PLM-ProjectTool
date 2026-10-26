# CR-PLAN-012：PlanVersion Review GET 前端只读兼容

- 日期：2026-10-26
- 状态：`AUTHORIZED_FOR_IMPLEMENTATION_BY_CR-EXEC-002`
- 来源 WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P05-A02`
- 基线：Gate 2 冻结 API-04 `PLAN_VERSION_SUBMIT_REVIEW`、`REVIEW_GET`；现有 ProjectReviewClient/View；PlanVersion 固定版本详情路由

## 差异证据（编码前）

- 补齐 `PLAN_VERSION_SUBMIT_REVIEW` 负责人授权策略后，Edge 确已通过真实提交，返回 `201` 并创建固定 Review/Round。
- Review 只读 API 成功返回，但当前 `ProjectReviewClient` 的主体类型/策略严格解析器没有 `PLN-02` 与 `PLAN_VERSION_ALL_V1`，因此合法只读响应会被拒绝；Review 页面也将未识别主体误呈为结构化专项。
- 这是既定 Review GET 合同与 PlanVersion 送审结果之间的前端消费缺口，不改变 API 投影、主体权限、评审规则或决定行为。

## 方案、风险与回退

- 方案：只扩充 Review GET 的前端严格 allowlist 与标签，识别 `PLN-02`/`PLAN_VERSION_ALL_V1`，显示固定 PlanVersion ID；不拼造 plan_id 或猜测详情 URL。Review 决定命令保持原样，不改授权或回执合同。
- 风险：类型/策略配对必须精确，错误配对应继续失败关闭；计划版本固定链接需要 PlanId，但冻结 Review GET 未返回 PlanId，故本轮不生成不可验证的链接。
- 回退：移除新类型、标签与测试；不涉及数据库/API或已有业务数据。
- 验证：Review client/view 定向测试、相关前端全量/typecheck/build、真实Edge→HTTP→PG由合成Customer Manager登录后读取Review并核对零决定/仍IN_REVIEW；随后完整后端/安全扫描。

## 授权结论

依用户持续自主执行授权与 `CR-EXEC-002`，先记录差异后实施。仅补足只读消费能力；Gate/Pilot/正式发行仍按既有证据判定。
