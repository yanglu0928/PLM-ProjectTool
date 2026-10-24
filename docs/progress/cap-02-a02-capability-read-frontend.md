# CAP-02-A02：受权能力基线读取入口编码前检查

日期：2026-10-24；状态：`SOURCE_PASS`（实际 Edge/PG 未验）。

|检查项|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `CAP-02-A02`：只解决用户无法发现已受权全局能力基线及当前批准版本的问题|
|输入基线|Gate 2 冻结 Capability 五个 GET、CAP-01-A05-A07 Windows 装配、CAP-02-A01 静态前置；不改变 `/api/v1`、Schema、角色或审批机制|
|前置|后端按 DeploymentAdmin=`ADMIN_HISTORY`、普通活跃项目成员=`CURRENT_APPROVED` 分投影，签名游标绑定会话/可见性；前端已有 Session 视图及只读分页模式。正式密钥前置不阻断合成/源码测试。|
|模块/实体/API|仅前端 Capability read client、列表/详情、路由/导航及对应测试；消费 GET baselines、baseline、versions、version、items。实体为 Baseline/Version/Item 只读投影；不得拼接别的项目来源。|
|权限|页面仅在有身份、已改初始密码、DeploymentAdmin 或至少一个当前授权项目时请求；服务器负责最终受权。普通成员界面只表达当前批准，不把管理员历史状态或未批准版本表示为可用于 Handover。|
|验收|严格解析合同/游标、列表与版本/条目分页、导航与状态提示；无身份/角色/换项目成员或错误响应失败关闭；定向及前端全量/typecheck/build。实际 Win11 Edge/PG 与 Capability 创建/批准另验。|
|风险|当前数据库可能无正式批准 Baseline，空态应引导而非虚报；版本/条目与 Baseline 当前批准指针要按服务器投影呈现；前端显示不代替服务端审批。|

L2 界面决定见 `docs/decisions/decision-log.md`；此项无 Migration。先做受权发现页，随后独立任务补标准能力 GLOBAL 固定文档来源和基线创建/Review，不在本项捏造已批准内容。

## 独立验收

- 新增五个 GET 的严格只读客户端、全局列表/详情/版本/条目分页、主导航与路由。当前 Session 仅限制请求发起；服务器仍决定最终可见性；前端再次拒绝普通成员意外收到的未批准基线/版本。
- 定向客户端/视图/主导航：3 个文件、14 项 PASS；前端完整测试：164 文件、1887 项 PASS；TypeScript 检查及 Vite 生产构建 PASS。
- 首轮测试暴露了同步游标校验的测试断言方式，以及管理员换成员后 UI 断言预期问题；修正测试与会话变化清屏/重读后重跑通过。未改变后端权限、冻结 API、Schema 或数据。
- 尚未执行 Windows 11 Edge/PG 实际 Capability 浏览器链，数据库也未证明存在当前已批准正式基线；本项仅 `SOURCE_PASS`，不得推定 HND 版本前置满足或 Pilot/Gate 通过。
