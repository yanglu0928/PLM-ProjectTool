# EVD-01-A04-P03-A08-P18：GLOBAL 人工资格页面与原操作号保留

日期：2026-10-02；Phase 2 Platform Core；结果：`FRONTEND_GLOBAL_DECISION_COMPONENT_PASS / LOOKUP_AND_BROWSER_OPEN`。

编码前检查：输入冻结 GLOBAL 资格 POST、P16 受权固定来源/当前 GET 页面和 P17 客户端。只改 GLOBAL Evidence 页面与组件测试；无实体、API、Schema、权限或依赖变更。仅当前 DeploymentAdmin、固定 Viewer 与当前 CANDIDATE 同来源时展示人工结论/理由/勾选；请求发送前须将 actor/Evidence/原 Key 写入 sessionStorage 并读回确认。存储不可用或记录畸形失败关闭；未知结果保留 Key 并阻新裁定，不自动换号重试。

页面增加人工资格表单，并沿用固定来源校验、强 ETag、受控 POST。成功回执仅提示首次结果不是当前状态；未知/断线保留最小操作记录，刷新仍显示待核对并关闭新写。定向页面 8 项、前端全量 1,063 项、typecheck/build PASS；覆盖请求前保存、成功清理、断线刷新保留与存储失败零请求。只存 actor/Evidence/Key，不存理由或正文。

兼容：GLOBAL 页面增量，无 Migration；现有项目页面不变。回滚停用 GLOBAL 表单，保留服务端历史 Evidence/Audit/收据及浏览器待核对原 Key。精确回查按钮尚未接入，真实浏览器、跨会话恢复、正式发行信任和 Gate3未验；sessionStorage 记录丢失后不能臆造原 Key。
