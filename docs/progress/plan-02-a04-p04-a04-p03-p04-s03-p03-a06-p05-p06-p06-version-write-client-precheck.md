# A06-P05-P06-P06 PlanVersion 写客户端编码前检查

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P06`
- 结果：`PRECHECK_PASS`

## 范围与实现约束

- 本WBS仅增加PlanVersion三个冻结写操作的SessionClient桥接及严格前端Client：完整快照create、bodyless validate、固定`PLAN_VERSION_ALL_V1`的原子submit-review；不增加读取Client、版本页、路由或业务API。
- 三个路径分别对应冻结API-04：`POST .../plans/{plan_id}/versions`、`POST .../versions/{plan_version_id}:validate`（无body）和`POST .../versions/{plan_version_id}:submit-review`。创建body上限沿用后端8 MiB；送审仅四字段且未开放的`due_at`、`submission_note`固定显式null。
- SessionClient要负责验证canonical UUID、调用可信同源fetch、CSRF、幂等键、超时/单次请求和401清Session；不确定写结果不可自动重试或更换key。创建client负责项目写角色与Session授权的现有模式，validate/submit同样遵守其当前授权要求。
- Client成功解析必须严格核对状态码、trace header、Cache-Control及准确字段/ETag/Location（若冻结合同提供），不得透传未验证的响应对象。验证报告只表示服务器当前快照检查，不表示批准；送审201只表示进入IN_REVIEW。
- 定向验证覆盖三条精确路径/headers/body、bodyless validate、非法ID/Key/角色、超时的不确定结果与原Key保持、严格响应和错误状态映射；并运行前端全量测试、typecheck及build。页面与真实Edge留后续WBS。

## 依赖 / 风险

- 依赖已冻结API-04及后端P06-P04原子SubmitReview HTTP；本项不改API/Schema。
- 版本历史collection缺失、Output refs未支持、来源/License/身份正式信任、完整UI/Edge尚未解决；不因客户端通过而扩大结论。
- 编码前检查通过：合同路径与相邻Survey/Handover/Outline/Section client模式已核对；单项边界明确，无外部数据、客户数据、AI或正式数据库操作。

## 下一项

在本WBS范围内实现并验证PlanVersion SessionClient安全写桥接和窄Client；完成后进入PlanVersion固定版本工作页的单一UI切片。
