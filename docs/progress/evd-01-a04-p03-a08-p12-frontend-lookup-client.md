# EVD-01-A04-P03-A08-P12：资格操作前端回查客户端

日期：2026-10-01；Phase 2 Platform Core；结果：`FRONTEND_CLIENT_PASS / UI_OPEN`。

编码前检查：输入 CR-EVD-004、P10 双 Scope HTTP 合同及 P11 Windows 显式组合。范围仅前端 Session 传输与项目 Evidence 回查客户端/测试；无后端、Schema、冻结合同、权限或依赖调整。项目 PM/CustomerManager 当前身份才允许发起，Key 16～128 printable ASCII 且只放 JSON Body；Session/CSRF 同源、no-store、禁止跳转。响应必须是完整最小 Envelope，`COMPLETED` 的 EvidenceId/首次状态匹配，`UNCONFIRMED` 不推断失败。两种结果均 `is_current_state_proof: false`，没有自动重发或换 Key。

前端定向 5 项 PASS；全量 1,045 项 PASS、typecheck/build PASS。测试覆盖客户经理、Body-only 原 Key、未知、非法参数/无权、错 Evidence/多余字段、网络不确定、已知拒绝。首轮测试使用不存在的 `VIEWER` 角色，Session 合同正确拒绝；改用正式 `CUSTOMER_MEMBER` 后重跑通过，未改生产行为。

兼容：新增独立客户端和 Session 方法，现有 UI/后端不变；无迁移。升级：页面接入前该功能仅可由内部调用，不可声称用户可用。回滚为停止调用并移除新增客户端，后端收据历史保留。项目页面恢复、GLOBAL Admin 客户端、真实浏览器、正式信任源及 Gate 3 仍未验。
