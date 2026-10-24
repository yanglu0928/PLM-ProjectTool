# CAP-02-A05-P04-P03-A04-P02-A01：GLOBAL 评审固定内容受控读取服务

日期：2026-10-24；结果：`INTERNAL_SERVICE_PASS / HTTP_NOT_MOUNTED / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P04-P03-A04-P02-A01`，只补 `CR-CAP-006` 内部固定版本与条目读取。|
|基线/前置|Gate 2 原 Capability 普通目录与 PROJECT Review 不变；`CR-CAP-005` GLOBAL Review 读取和决定已通过隔离 HTTP/PG；`CR-CAP-006` 已先登记。|
|模块/实体/API|Review 应用服务，经 Capability 只读 Repository 读取已绑定 Version/Item；本片无 HTTP、ORM、Migration、新依赖。|
|权限/风险|每次同事务重验 License/当前 Session/当前启用用户/精确 GLOBAL CAP-01 Review/唯一首轮/受分配 Reviewer 或 DeploymentAdmin/Review 与固定 Version 双向引用；返回内容不构成批准资格。|
|验收|普通受分配者能读取 Version 和有限分页条目；未分配、错绑/跨版本、异常页、坏参数、License 拒绝失败关闭；后端完整回归。|

`GlobalCapabilityReviewReadService` 现在额外提供 `fixed_version` 和 `fixed_items`；后者每页最多 50 条，限定条目所属 Baseline/Version、严格序号和有效下一页位置。调用服务不授予通用能力目录历史查看权限。签名游标、HTTP 传输及文档跳转留待下一片，不能把内部方法声称为可用页面。

测试：定向 13 项/7 子例；后端全量 4090 通过、3 跳过、6136 子例，2 个既有警告。无实际 PG/HTTP/Edge 或真人核对证据；正式信任/安装/Gate/Pilot/Release 未通过。
