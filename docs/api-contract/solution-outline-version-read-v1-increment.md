# Solution OutlineVersion 历史读取 V1 增量投影

日期：2026-10-09；WBS：`SOL-03-A05-A03-P02`。依据 Gate2 冻结 API-04 的 `SOL_OUTLINE_VERSION_LIST/GET` 路径和 Project member 权限；本文件只明确当时未细化的返回投影，不修改冻结路径、角色或 CREATE。

## GET

`GET /api/v1/projects/{project_id}/solution-outlines/{outline_id}/versions/{outline_version_id}`。当前有效项目成员、可信 Host、Session 和 License 均由服务端校验，目录/版本按 ProjectId 隔离。成功 200：`{data, trace_id}`，`Cache-Control: no-store`；`data` 包括版本/目录/项目 ID、`version_no`、`version_state`、SHA-256 `content_fingerprint`、三类计数、缺失/冲突声明计数、前驱/Review 引用、创建人/时间，以及按创建时顺序固定的 `section_ids`、`requirement_refs`（根/版本 ID）、`reference_refs`（PROJECT/GLOBAL Scope 与根/版本 ID）、完整缺失/冲突声明。无 ETag；不返回来源正文、Locator、管理员凭据，也不将历史引用表示为当前合格。

## LIST

`GET /api/v1/projects/{project_id}/solution-outlines/{outline_id}/versions?page_size=1..100&cursor=...`。默认页大小 50，按 `version_no` 倒序。成功 200：`{data:{items,next_cursor,has_more},trace_id}`；`items` 只含 GET 的版本元数据及计数，不批量返回固定引用或声明正文。游标由独立 HMAC-SHA256 key 签名，绑定 Session、Project、Outline、页大小与下一页前置版本号；重复/未知查询参数、非法/跨范围/篡改游标失败关闭。空版本目录返回空页；目录不存在返回 404。

可选路由未注入时 GET/LIST 均为 404；只读注入不开放 POST。当前只有 HTTP 合同单元验证，真实 ASGI/PG、Windows 独立游标签名密钥供给/恢复及 UI/浏览器另项验收。错误仍沿 API-01 统一安全投影；`AUTH_ACCESS_DENIED` 401、资源不可见 404、License 403、非法页 422、畸形游标/查询 400、未知后端异常 503。无 Schema/Migration。

TraceLink：Gate2 API-04 → A05-A02 历史 Owner → DEC-1146 → A05-A03-P01 游标 → 本增量投影 → Windows/浏览器。
