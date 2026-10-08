# CR-SOL-010：GLOBAL 人工确认/撤回的原操作号受权回查

日期：2026-10-09；状态：按 CR-EXEC-001 持续授权实施，Owner/API/Windows隔离PG/前端合同已验；Edge与真实人工业务判断未验。原 Gate 2 API-04 提交 `64cdf09` 与 CR-SOL-009 增量合同均保留历史，不追写。

## 冲突、证据与决定

CR-SOL-009 的 Confirm/Revoke 已具持久幂等收据，同 Key 重放在隔离 PG/HTTP 可保持单次效果；但浏览器超时或断连后不知道首次是否提交。仅保存 Key 并让人勾选“已核对”来清除本地待处理状态，无法客观证明服务端已完成，也可能让新 Key 再提交一次确认。证据为 P08-P04-P02 页面设计复核、既有 Evidence Eligibility 原 Key 回查模式。当前 P04-P02 页面代码尚不计 PASS，不将该缺口当作人工确认完成。

选择兼容新增只读 POST `.../reference-deidentification-confirmations:lookup-operation`：请求含原 `operation_key` 与 `operation_kind`（CONFIRM/REVOKE），当前 Session/CSRF、可信 Origin、有效 License、DeploymentAdmin 和 actor-scoped Receipt 查询，返回 `UNCONFIRMED` 或 `COMPLETED`、最小确认 ID/首次状态；不带客户正文/来源路径、不泄露其他 actor 结果。若确认存在，还须返回当前确认状态 `CONFIRMED`/`REVOKED` 与最新有效性事实，避免历史回执冒充当前资格。未找到收据必须称 `UNCONFIRMED`，不称“肯定未提交”；客户端不自动换 Key、不自动提交。只读查询不创建 Audit/收据。仅在客观 `COMPLETED` 且当前状态核对后，页面可清除本地待核对锁；`UNCONFIRMED` 保持提示和原 Key。

替代方案“不提供回查、由用户手工清理 sessionStorage”拒绝，因证据不足和重复提交风险；“超时自动换 Key 重试”拒绝，因可能双写；“自动重放原 Key”也不采用为默认恢复，避免来源/权限已变化时误解返回。此前已实现但未验收的本地解除锁按钮须移除或改为以上客观回查。

## 差异、风险、迁移/回滚与验证

这是对冻结 `/api/v1` 的新增可选操作，不改既有 Confirm/Revoke 请求/响应。无新 Schema/依赖；复用现有持久 Receipt 和确认记录。风险：收据暴露跨管理员操作、旧确认已撤回被误当有效、网络查询不确定被误报未提交。先鉴权再按当前 actor 和操作种类构造收据 Scope，返回最小状态；错误和越权失败关闭。回滚停用新查询与 UI 恢复入口，保留已提交确认/Audit/Receipt，不删除历史；页面继续锁定不确定操作。

验证：单元/合同覆盖同 actor 原 Key、不同 actor/操作种类/错误来源、未找到、Confirm 后 Revoke 后当前状态、CSRF/License；隔离 PG/ASGI、Windows 显式写模式及前端恢复交互/Edge。完成前不得将 P04-P02 页面、真人确认或 Gate 3 标为 PASS。

TraceLink：冻结 API-04 → CR-SOL-009/P03-P05 → P04-P02 页面安全复核 → 本 CR → 回查 Owner/API/Windows/客户端/UI/PG/Edge。
