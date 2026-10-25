# CR-PLAN-005：PlanVersion受控代码目录

日期：2026-10-26。状态：`AUTHORIZED_FOR_IMPLEMENTATION_BY_CR-EXEC-001`；非Gate通过。

## 发现

PlanVersion字段映射（CR-PLAN-002/S01）要求 `calendar_ref`、WBS `category` 与 `support_role_refs` 由版本化白名单解析；当前仓库只有语法校验和文本列，没有目录/配置或Project维护Owner。若直接接受任意合法代码，就没有满足受控映射；若静默按Project角色套用，则会混淆业务协作角色与授权角色。

## 方案

- A：接受所有符合格式的字符串。拒绝：不满足受控目录约束，易形成不可解释或拼写分叉的正式快照。
- B：提供内部不可变 `PLAN_WBS_CODES_V1` registry，精确匹配未知值即失败关闭；后续若需客户自定义，另建版本化目录/管理接口和数据迁移。
- C：新增数据库目录表和维护API。拒绝：超出当前单一内部Plan Owner任务，需新Schema/API/管理权限设计。

选择 B。首版集合为：

- WBS category：`ANALYSIS`、`DESIGN`、`IMPLEMENTATION`、`TEST`、`DEPLOYMENT`、`TRAINING`、`ACCEPTANCE`、`PROJECT_MANAGEMENT`、`OTHER`。
- Support role：`PROJECT_MANAGER`、`IMPLEMENTATION_MEMBER`、`CUSTOMER_MANAGER`、`CUSTOMER_MEMBER`，沿用字段映射明确要求的Project role code vocabulary；这只是WBS快照标签，不授予任何授权，执行人仍由 `owner_ref` 和授权服务单独验证。
- Calendar：`CN_WORKDAY`（作为当前已有输入示例使用的逻辑code；工作日换算语义不扩展，准确日历算法留待正式调研配置）。

拒绝未列值，不做大小写别名或自动猜测。`OTHER`仅为显式类别值，不接受任意自定义代码。冻结API/Schema无变化；部署无需迁移。回滚时可撤去Owner/registry，保留已创建不可变版本，不静默重写历史。风险是用户现有业务术语可能不在首版集合内；在用户配置界面可用前须由调用方使用列出的规范代码。

## 验证

Owner unit/PG必须覆盖每个有效代码、未知类别/角色/日历拒绝、顺序/重复输入、无数据副作用及完整事务回滚。实际行业/客户分类适配不宣称已调研确认。

## 授权与边界

按持续自主执行授权先记偏差后实施；本CR不授权跨客户数据外发或更改冻结API/Schema。首版只在本产品内部Plan Owner生效；Gate/Pilot/Release仍按各自证据验收。
