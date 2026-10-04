# EVD-01-A04-P03-A08-P19：GLOBAL 原操作号精确恢复入口

日期：2026-10-02；Phase 2 Platform Core；结果：`FRONTEND_GLOBAL_RECOVERY_COMPONENT_PASS / BROWSER_OPEN`。

编码前检查：输入 CR-EVD-004、P14 管理员收据客户端、P15 当前 GET、P18 请求前原 Key 会话记录。仅改 GLOBAL Evidence 页面与测试；无 API、Schema、角色或依赖变化。只在同一当前 DeploymentAdmin/原 actor/原 Evidence 的有效待核对记录下回查；`UNCONFIRMED` 继续锁定。`COMPLETED` 后另行受权读取当前 Evidence 强 ETag，分开展示历史收据和当前资格；人工点击后才清除会话记录，存储失败继续保留。

GLOBAL 页面增加“按原操作号回查”和人工解除提醒。组件测试覆盖历史完成后当前已撤销、未知收据、当前 GET 故障、禁止自动清理及零资格重发；页面定向 10 项、前端全量 1,065 项、typecheck/build PASS。历史结果不被当作当前业务事实，Key 不进入 URL/长期存储。

兼容：前端页面增量，后端/Schema/冻结 API 不变；无迁移。回滚隐藏回查入口并保留原 Key 和服务端收据。真实浏览器、跨会话 Key 丢失恢复、正式信任源和 Gate3仍未验；组件测试不能代替实际 UAT。
