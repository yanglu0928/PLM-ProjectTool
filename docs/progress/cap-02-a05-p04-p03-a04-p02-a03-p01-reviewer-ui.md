# CAP-02-A05-P04-P03-A04-P02-A03-P01：固定内容评审人页面

日期：2026-10-24；结果：`FRONTEND_CONTRACT_PASS / EDGE_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2；本片只解决 CAP-01 GLOBAL 固定版本可见与受分配评审人页面，不代做包内/真人验收。|
|基线/前置|`CR-CAP-005` 精确 Review 决定客户端和 `CR-CAP-006` 固定内容 HTTP/Windows 11 隔离 PG 已通过；冻结 PROJECT API 与普通 Capability 目录不变。|
|模块/API/数据|仅前端路由、Review 客户端/页面与来源链接；复用现有 Capability 安全解析器，不改后端、ORM、Migration 或外部依赖。|
|权限/安全|客户端精确核对 Review/轮次/版本/ETag 和有界签名页；必须读完声明的全部条目才允许已分配者作决定。服务端每次读/决定仍独立重验当前身份和来源。|
|异常/回滚|决定操作号在 SessionStorage 原样保留供不确定结果重试；确定拒绝清除，轮次变化/冲突/回执与当前状态不一致时停止。撤前端入口不删除合法 Review/Audit/收据。|
|验收|已分配普通用户核对内容后批准、未分配无按钮、未确定结果原号恢复、条目缺失失败关闭；前端全量/typecheck/生产构建。|

新增 `/capability-baselines/:baselineId/versions/:versionId/reviews/:reviewId` 页面；管理员可从能力版本详情或送审回执进入，并可把精确链接交给指定评审人。页面按签名游标读取完整固定条目、文档版本及 Evidence 引用，显示评审人/已作决定，核对勾选后才允许批准或填写退回意见。没有新增普通 Reviewer 的全局待办发现页；该入口仍依赖直接链接。文档/Evidence 目前仅显示固定引用标识，不声称可一键定位正文。

客户端复用通用 Capability Version/Item 的严格解析器，但访问路径只走 Review 作用域的两条 GET；不扩大通用目录权限。前端定向 Review/页面测试 11 项；全量 179 文件、1947 项通过，TypeScript 类型检查和 Vite 生产构建通过。已知构建大分块警告未恶化为失败。尚未运行这版页面的 Edge/包内/真实用户/正式信任或多平台验收；下一片 `A03-P02` 单独做 Windows 11 Edge 与 PG 闭环，之后 P05 非发行候选包。
