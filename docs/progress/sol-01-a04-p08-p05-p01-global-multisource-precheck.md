# SOL-01-A04-P08-P05-P01：GLOBAL 多来源人工核查入口前置核查

日期：2026-10-09；结果：`MULTISOURCE_UI_PRECHECK_PASS`，仅合同/代码与现有证据对账，不代表多来源 UI 或真人确认通过。

编码前检查：Phase 2；前置 P04-P03 的 Win11 Edge/隔离 PG 单来源链通过，Gate 2 冻结 API-04 保留，CR-SOL-009/010 的兼容增量仍有效。输入为 `ReferenceSourceQualificationService`、GLOBAL Preview/Confirm/Revoke/回查、`EvidenceListClient`/Viewer、当前单来源页面和 `SOL_REFERENCE_CREATE` 冻结操作。涉及 Solution 前端入口与既有受权 Evidence/Document 读取；不改数据模型、公开 API、权限或 License。验收是确定多来源选择/固定版本/逐条核查/预览漂移/原 Key 锁定的安全边界；本项不运行新程序测试。

发现：现有 Preview/Confirm 后端接受有序 1～100 个 DocumentVersion 与 0～500 个 Evidence，并在同事务逐个证明、对整个集合计算指纹；GLOBAL Reference 创建也使用同一来源集合资格。当前页面从一条 GLOBAL Evidence 进入，固定为一个 DocumentVersion/一个 Evidence，所以不能构造多来源集合。单条 Evidence Viewer 已返回受权固定文档根/版本和原文 URL；GLOBAL 列表可分页，资格 GET 提供当前状态。服务端仍须在预览/确认/未来创建时独立重验，前端勾选不是来源或脱敏事实。

决定：P05-P02 单独增加多来源候选选择与核查页面，不改现有单来源入口；选择项只来自当前管理员受权 GLOBAL Evidence 列表，按选择顺序保留 Evidence ID，并从逐项 Viewer 提取 DocumentVersion，首见去重且保留顺序。每条显示固定版本、定位精度和受权原文链接；每次 Preview 前逐项重新读取 Viewer/当前资格，只有逐项打开、逐项核对且本人声明才允许 Confirm。任一来源/分类/选择变化清空 Preview 和勾选；来源漂移 409 清空全部待确认状态。限制 100 个唯一版本和 500 条证据，重复或错 Scope 失败关闭。网络不确定仍用原 Key 锁定并按 CR-SOL-010 回查，不从历史回执推断现时资格。P05-P03 用隔离 PG/Edge 证明至少两个不同 DocumentVersion、两个 Evidence 的顺序/原文绑定、漂移和恢复；不能用自动脚本代替实际人工核查。

偏差/迁移/回滚：现有 API 与服务端多来源语义兼容，无新 Change Request、Schema/依赖/数据迁移。新增 UI 可通过不暴露入口回滚，历史确认/Audit/收据不得删除。风险为分页遗漏、重复文档引用、前端把旧 Viewer/预览当现时证明、跨会话待核对操作丢失；上述约束与服务端写时证明同时保留。GLOBAL Create 在多来源入口、实际业务确认和正式信任源就绪前继续关闭。Server 2025、20 并发/Gate 3/发行未通过；Debian 13 依用户指令跳过。

TraceLink：冻结 API-04 → CR-SOL-009/010 → P04-P02 单来源 → P04-P03 Edge → 本 P05-P01 → P05-P02/P03 → GLOBAL Create 前置。
