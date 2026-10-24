# HND-05-A05-P03：交接评审详情正确标识与来源入口

日期：2026-10-25；状态：`HND_05_A05_P03_REVIEW_VIEW_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `HND-05-A05-P03`；只修 PROJECT Review 详情对 HND-02 的标签、固定版本展示和来源入口，不改 Handover 页面。|
|输入基线|Gate 2 Review/HND 合同、P01 安全 GET、P02 严格客户端、既有通用 Review 详情。|
|前置|HND 送审已有已知 ReviewId 路由；当前页面非 SOL-03/05 都误落结构化专项分支。|
|模块/实体/API/权限|仅前端 Review 详情与测试；不改 API、Schema 或角色，决定仍按当前 Assignment/Session 且必须显式核对。|
|验收|显示交接分析与本轮固定版本 ID，进入交接分析而不误跳专项方案；不声称列表包含 HND 或当前分析页会自动定位固定版本；原 SOL 三类回归及全量前端/typecheck/build。|
|风险/回滚|用户仍需在交接分析页手动选取页面展示的固定 VersionId；精确深链留独立 Handover 页面任务。回退仅前端资源，已形成 Review/Audit 不删；真实 Edge/PG/包内与客户决定另验。|

编码前置满足。不能用普通分析页链接冒称已定位固定版本。

页面现区分 HND-02 与 SOL-03/05/06：展示“交接分析评审”、本轮固定
HandoverVersionId、实际交接分析入口及显式“按上述 ID 选取版本”指引；
不再误显示结构化专项标签/专项固定版本链接，也不把仅 SOL 主题的评审列表
当成交接返回路径。既有 Assignment/Session/原号决定和人工确认文案保持。
定向 6 项、前端全量 188 文件 2,010 项、typecheck/生产构建退出 0。

本片没有精确版本自动定位。下一片 `HND-05-A05-P04` 仅在交接详情实现
经服务端精确 `getVersion` 证明的固定 VersionId 深链；真实 Edge/PG/包内决定
仍另行验收。真人客户确认、正式信任/安装、Pilot/Gate/Release 未通过。
