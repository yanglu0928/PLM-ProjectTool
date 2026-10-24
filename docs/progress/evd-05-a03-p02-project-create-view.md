# EVD-05-A03-P02：项目 Evidence 候选创建页面

日期：2026-10-25；状态：`FRONTEND_VIEW_PASS / PACKAGED_PROOF_PENDING`。

|编码前检查|结论|
|---|---|
|当前 Phase/WBS|Phase 2 / `EVD-05-A03-P02`；只补 PROJECT Evidence 整文档候选的可操作页面。|
|输入基线|冻结 PROJECT Evidence POST、现有项目文档列表/固定版本 GET、P01 安全客户端、HND-05-A02 来源前置。|
|前置任务|P01 定向4/全量1957/typecheck/build PASS，后端 Windows 写组合已有 POST；当前项目 Evidence 列表仅能读/核定。|
|涉及模块/实体/API|Evidence CANDIDATE、PROJECT DocumentVersion；既有受权 GET/POST，不改后端 API/Schema。|
|权限|PROJECT_MANAGER/IMPLEMENTATION_MEMBER 可创建；当前会话和项目切换需阻止旧响应落入新页面；服务端仍为最终授权。|
|验收|浏览器按项目选择 ACTIVE 文档的 AVAILABLE 固定版本，整文档定位与提示标签；原号/原输入恢复、未知结果不换号、CANDIDATE 明示，权限/来源负例、定向及完整前端回归。|
|风险|整文档 Evidence 不能精准定位页/段；人工资格仍需另行核定，包内 Edge/PG 待 P03，不能宣称 HND 正式版本链已打通。|

本片沿用已验证的全局 Evidence 页面交互，但 PROJECT 权限、来源与待确认操作号按项目隔离；页面不自动核定资格，不生成问题事实。

Changed：新增项目 Evidence 创建页与列表入口，选择 ACTIVE 项目文档及 AVAILABLE 固定版本，只提交 DOCUMENT locator 与用户标签；原来源/操作号按用户和项目写入会话存储，结果不明时经人工核对后同号重试，成功只显示 CANDIDATE。Files：`ProjectEvidenceCreateView.vue`、对应测试、`ProjectEvidenceListView.vue`、`app/router.ts`。Migration/API：无 Schema、后端 API 或权限变更。Tests：定向4/4、前端完整1961/1961、typecheck/build退出0。Result：`EVD_05_A03_P02_FRONTEND_VIEW_PASS`。Known Issues：未在新随包源码的 Edge/HTTPS/PG 上验收；当前整文档定位不能精确定位页/段，资格必须由当前项目有权人员独立确认；旧候选包不含本页。Next：`EVD-05-A03-P03` 新非发行候选重建及 Win11 包内项目 Evidence 创建/资格/PG/Audit 端到端。
