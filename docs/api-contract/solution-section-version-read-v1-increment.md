# Solution SectionVersion 历史读取 V1 增量投影

日期：2026-10-12；WBS：`SOL-05-A03-P03`。依据 Gate2 冻结 API-04 的 `SOL_SECTION_VERSION_LIST/GET` 路径和 Project member 权限；本文件细化未冻结的返回投影，不改路径、角色或 CREATE。

`GET /api/v1/projects/{project_id}/solution-sections/{section_id}/versions/{section_version_id}` 在当前可信 Host、Session、License 和 Project 成员授权下返回 200 `{data,trace_id}`、`Cache-Control: no-store`。`data` 包含 Project/Section/Version ID、版本号/状态、标题、受控正文 DocumentVersion 或 ArtifactRef 二选一、32 字节指纹的 hex、Requirement/Evidence 固定引用及声明、前驱/Review 引用、创建人/时间。历史固定引用不表示目前仍合格；不返回正文/Locator/来源路径/管理员凭据。

`GET /api/v1/projects/{project_id}/solution-sections/{section_id}/versions?page_size=1..100&cursor=...` 默认页大小50、版本号倒序。成功返回 `{data:{items,next_cursor,has_more},trace_id}`，`items` 只含版本元数据、标题及计数，不批量返回固定引用或声明正文。游标由本资源族独立32字节 HMAC-SHA256 key 签名，绑定 Session、Project、Section、页大小及下页版本号。重复/未知查询参数、非法/跨资源/篡改游标失败关闭。空 Section 历史返回空页，Section 不存在404。

可选路由未注入时两个 GET 均404；只读注入不拦截现有 POST CREATE。错误按 API-01 安全投影：会话401、资源不可见404、License403、非法页422、畸形查询/游标400、内部故障503。无 ETag、Schema/Migration。本项仅 HTTP 合同，真实 PG/Windows 独立密钥供给/UI/浏览器留后续 WBS。

TraceLink：Gate2 API-04 → CR-SOL-003 → A03-P02 Owner → DEC-1183 → 本增量 → Windows/浏览器 → Gate3/Pilot。
