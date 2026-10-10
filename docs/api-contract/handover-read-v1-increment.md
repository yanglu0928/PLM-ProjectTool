# Handover Analysis 五个读取 HTTP V1 增量

日期：2026-10-05。实现基线：冻结 API-01/API-04、DM-05、Schema0102 与 DEC-871；不增加或改名 Operation。

## Operation 与投影

|Operation|路径|安全投影|
|---|---|---|
|`HND_ANALYSIS_LIST`|GET `/api/v1/projects/{project_id}/handover-analyses`|Analysis 摘要页、强 ETag 值、签名续页 cursor|
|`HND_ANALYSIS_GET`|GET `/api/v1/projects/{project_id}/handover-analyses/{analysis_id}`|Analysis 安全详情与响应 ETag|
|`HND_VERSION_LIST`|GET `.../{analysis_id}/versions`|不可变 Version 摘要页|
|`HND_VERSION_GET`|GET `.../{analysis_id}/versions/{analysis_version_id}`|固定来源 DocumentVersion、Capability BaselineVersion、AI Task 引用与计数|
|`HND_VERSION_ITEM_LIST`|GET `.../{analysis_id}/versions/{analysis_version_id}/items`|问题清单、输入规格、Evidence/Capability 固定引用与候选项|

所有入口仅接受 canonical lowercase non-zero UUID。列表只接受唯一的 `page_size/cursor` query，页长默认 50、范围 1～200；详情拒绝任何 query。响应均为 `data/trace_id` Envelope 和 `Cache-Control: no-store`，不返回文件路径、文档/Evidence正文、AI输入输出、Secret或内部表字段。

## 三类独立 cursor

- Analysis cursor 使用独立 32 字节密钥，绑定 Session、Project、页长和完整 `(updated_at, analysis_id)` 位置。
- Version cursor 使用另一密钥，绑定 Session、Project、Analysis、页长和 `version_no`。
- Item cursor 使用第三把密钥，绑定 Session、Project、Analysis、Version、页长和 `ordinal`。

三类 token 均为 canonical JSON + HMAC-SHA256，篡改、错钥、跨会话、跨项目、跨父资源、跨资源族或改页长均返回 400；原始位置不由客户端直接提供。续页仍由 Owner 在当前事务重验 License、当前 User 和项目成员事实。

## 兼容、错误与回滚

权限或资源隔离失败统一 404；License 403；归档项目 409；字段/页长 422；畸形 query/cursor 400；异常投影或内部失败 503。本增量无 Migration、依赖、外部网络、客户数据外发或现有冻结 URL 破坏。Router 仅显式注入，默认应用保持五路 404；A07 才接 Windows 生产组合与正式 Vault key。回滚可停止注入 Router，数据历史不变。
