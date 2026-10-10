# Capability 五个读取 HTTP V1 增量

日期：2026-10-05。实现基线：冻结 API-01/API-04、DEC-840/841；不增加或改名 Operation。

## 通用边界

Router 仅通过 `create_app(capability_read_router=...)` 显式注入，默认五路均为404；A05-A06不进入Windows生产组合，该接线留给A05-A07。所有读取要求可信Host、当前`plm_session`和有效License，响应使用冻结`data/trace_id` Envelope及`Cache-Control: no-store`。

列表只接受唯一`page_size/cursor`，page size默认50、范围1～200。游标分为Baseline与子资源两个独立32字节HMAC密钥域，绑定Session、页大小、当前权限投影、资源族及上级资源。续页时Owner在同一读取事务重算权限投影，如与游标不符则失败关闭。ID只接受canonical lowercase non-zero UUID。

## Operation

|Operation|路径|成功结果|
|---|---|---|
|`CAP_BASELINE_LIST`|`GET /api/v1/global/capability-baselines`|Baseline page + opaque next cursor|
|`CAP_BASELINE_GET`|`GET /api/v1/global/capability-baselines/{baseline_id}`|BaselineView + 强ETag|
|`CAP_VERSION_LIST`|`GET .../{baseline_id}/versions`|immutable Version page|
|`CAP_VERSION_GET`|`GET .../{baseline_id}/versions/{baseline_version_id}`|Version、来源摘要与Review逻辑引用|
|`CAP_VERSION_ITEM_LIST`|`GET .../{baseline_version_id}/items`|CapabilityItem page及DocumentVersion/Evidence逻辑引用|

DeploymentAdmin可读受控全历史；非管理员必须是至少一个ACTIVE Project/Department的当前ACTIVE Member，且仅读ACTIVE Baseline当前APPROVED Version/Items。无权、撤权、历史或不存在均收窄为404；License返回403，参数/游标投影冲突返回422，未知内部失败83。不返回数据库表、物理文件位置、原文、评审意见、异常或Secret。

本增量无Schema/Migration/依赖/网络/外发。停止注入Router可关闭新读取，数据历史不变。
