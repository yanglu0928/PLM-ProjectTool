# CR-CAP-003：Capability 送审时限与备注兼容收窄

- 日期：2026-10-05
- 状态：`APPROVED_BY_STANDING_AUTHORIZATION`
- 范围：`CAP-01-A05-A05`，冻结 `CAP_VERSION_SUBMIT_REVIEW`
- 基线：Gate 2 原冻结提交 `64cdf09` 保留；Review/Capability 当前 Schema0095 不追写

## 差异与原因

冻结送审请求包含 `due_at` 和 `submission_note`，但冻结 Review 数据模型、Schema0034/0035 及现有 GLOBAL 持久化内核都没有对应字段或不可变历史载体。若 HTTP 接受非空值却丢弃，会把用户输入伪装成已保存事实；若临时写入 Audit reason，会扩大日志语义并且无法完整重放结构化数据。

## 方案

保留冻结四字段请求形状；首版仅接受 `due_at:null` 和 `submission_note:null`，任一非空即以 422 失败关闭，不静默丢失。送审仍使用冻结策略 `DEPLOYMENT_ALL_V1`，不增加临时调度表或 Capability 私有 Review 字段。

后续如启用时限/备注，必须以通用 Review 能力新建 Schema/API Change Request，定义所有 Subject 共用的不可变存储、时区、修改/撤回和重放语义，不得只为 Capability 跨 Owner 补列。

## 风险、迁移与回滚

- 风险：调用方必须显式传空值，无法在首版设定送审截止时间或备注；此限制比丢数据更安全。
- 迁移：无 Schema/Migration/依赖/配置/网络或历史数据变化。
- 回滚：不注入送审 Router 即关闭新 HTTP 流量；已形成的 Review/Subject/Audit/幂等收据保留并向前修复。
- 验证：合同测试覆盖严格四字段、两非空负例和默认 404；应用/真实 PostgreSQL 覆盖原子送审、回滚、重放及当前权限。

依据用户持续授权，本偏差在记录风险和回滚后直接实施；不改变 Gate 3、正式信任、客户数据外发或发行验收要求。
