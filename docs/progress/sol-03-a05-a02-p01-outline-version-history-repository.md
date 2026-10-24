# SOL-03-A05-A02-P01：OutlineVersion 固定历史仓储重建

日期：2026-10-09。结果：`SOL_03_A05_A02_P01_OUTLINE_VERSION_HISTORY_REPOSITORY_PG_PASS`；仅 Solution 仓储与内部只读 DTO，未开放受权 Owner/HTTP/UI。

## 编码前检查

|字段|核查|
|---|---|
|Phase/WBS|Phase 2 Platform Core / 本任务|
|输入基线|Gate2 冻结 `SOL_OUTLINE_VERSION_GET/LIST`；`0155` 不可变首响、`0156` 受限固定集合；A05-A01 读取授权|
|前置|双 Scope CREATE 已在 Win11/隔离 PG 写入版本、三类有序关联及首次结果|
|模块/实体|Solution 仓储及内部 `OutlineVersionHistoryView`；版本、Section、Requirement、Reference 固定关联和首响|
|API/权限|不开放 API；后续 Owner 必须按项目成员、License、Session 重验|
|验收|同项目 GET/按版本号倒序分页；三类关联顺序、计数、Scope/归属和首响一致；跨项目不可见、非法页及缺项乱序拒绝；PG 双 Scope 与全量回归|
|风险|历史固定引用不等于来源当前仍合格；DTO 不声称资格、批准或客户确认|

## 实施与验证

新增历史 DTO 与 `SqlAlchemyOutlineVersionReadRepository`。GET 以版本/目录/项目三重身份定位，联读不可变首次回执，并按 ordinal 重建三类关联；拒绝计数/序号、Scope 归属、重复根或首响不一致。LIST 按 `version_no` 倒序并复用同一 GET 完整性检查，不静默丢弃异常行。未复制来源正文或 Locator，也不拿创建首响替代现时版本状态。无 ORM/Schema/Migration、冻结 API、角色或依赖变化。

Win11 两套全新隔离 PostgreSQL 18.6 复用已验真实 PROJECT/GLOBAL 创建夹具：版本 2→1 分页、固定三类引用、原版本 GET、跨项目/错目录不可见和非法页拒绝均退出 0。首轮 GLOBAL 验收脚本误认为旧夹具回调含项目 ID，失败于测试适配；已改从隔离库固定关联反查，再于全新库双 Scope 重跑通过。定向单元 2 项/3 子例；后端全量 3458 通过、3 跳过、5295 子例。构建/发行未在本项运行。

回滚：撤未接线的历史读取 DTO/仓储与验证资产即可；已有版本、首响、关联及 Audit 均保留。已知限制：实际受权读取 Owner、GET/LIST HTTP、Windows 装配、前端版本详情/浏览器仍待；GLOBAL 项目候选发布见 CR-SOL-018，Gate3/UAT/正式信任/Server2025/发行仍未通过。下一项 A05-A02-P02 组合受权读取 Owner。

TraceLink：Gate2 API-04 → `0155/0156` → A05-A01 只读授权 → 本历史仓储 → A05-A02-P02 Owner → HTTP/UI。
