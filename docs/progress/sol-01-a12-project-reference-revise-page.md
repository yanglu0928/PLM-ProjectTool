# SOL-01-A12-P02：PROJECT Reference Revise 受控来源页面

日期：2026-10-09。结果：`SOL_01_A12_P02_PROJECT_REVISE_PAGE_PASS`；这是前端页面/路由合同和构建验证，不是浏览器/PG 或正式用户验收。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-01-A12-P02；输入冻结 API-04、CR-SOL-013/015、A07～A11、A12-P01，前置满足。
- 模块/实体/API/权限：仅 PROJECT Reference 页面、项目文档固定版本/Evidence 来源选择和现有 A11 写客户端；提交仅 PROJECT_MANAGER/IMPLEMENTATION_MEMBER，其他角色不读取写页候选。无 Schema/Migration、后端、依赖或冻结 API 变化。
- 验收：活动且允许类别文档的受权固定 AVAILABLE 版本必选、Evidence 可选且须对应已选版本；每项独立核查勾选、当前根/来源提交前重核、未知结果原 body/If-Match/Key 锁定与同键恢复、历史 201 与刷新当前详情分离；路由与页面定向、前端全量、typecheck/build。
- 风险：前端文档/证据 GET 是受权元数据和当前视图，不证明提交瞬间文件字节/权限；服务端写事务仍会重新证明。会话存储不可读或损坏时失败关闭，新 Key 不自动生成以绕过旧操作。

## 实施与验证

新增 `/projects/:projectId/reference-solutions/:referenceId/revise` 页面，并从当前详情按角色显示入口。页面不提供 UUID 自由填写；通过项目文档列表→可用版本选择和可选项目证据列表→受权 viewer/当前资格选择固定来源。文档/证据逐项核查、分类和总确认后，先重新 GET 当前 Reference 并重新 GET 已选文档版本及证据资格，再将原请求材料和幂等键写入会话存储后单次 POST。未知结果锁住新提交，仅允许显式同键恢复；成功回执标为历史首次结果并重新 GET 当前根。

定向页面 7 项覆盖客户角色拒写、无 Evidence 合法链、实施成员证据链、中文业务分类、根版本变化、网络未知同键恢复、损坏会话存储拒写；前端全量 119 文件/1692 项通过，typecheck 与 production build 通过。Build 报现有主包超过 500 kB 的非阻断提示；未运行真实 Edge/PG，A12-P03 需单独验收。

## 兼容/回滚/后续

纯前端增量，移除路由与详情入口可关闭页面，数据库历史不受影响。TraceLink：API-04 → CR-SOL-013/015 → A07～A12-P01 → DEC-20261009-1131 → 本 P02 → A12-P03 Win11 Edge/隔离 PG → A13 GLOBAL 整合。正式目标账户、20 并发、Server2025、Gate3/UAT/可用程序包仍待；Debian13 实机依指令暂跳过。
