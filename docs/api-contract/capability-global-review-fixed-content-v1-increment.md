# Capability GLOBAL Review 固定内容 V1 增量合同

日期：2026-10-24；状态：`CR-CAP-006 / WINDOWS_11_SYNTHETIC_HTTP_PG_PASS / UI_PENDING`。原 Gate 2 API-02/API-04 冻结提交 `64cdf09` 不变。

|Operation|方法与路径|授权|成功|边界|
|---|---|---|---|---|
|`GLOBAL_REVIEW_FIXED_VERSION_GET`|GET `/api/v1/global/reviews/{review_id}/fixed-version`|当前 Session、License、DeploymentAdmin 或本轮受分配且启用 Reviewer，精确 `CAP-01` GLOBAL Review/唯一首轮/Version 双向绑定|200 固定 Version 安全投影、Review/Round ID、强 Review ETag、Trace/no-store|不授予普通 Capability 目录历史读取，也不返回正文|
|`GLOBAL_REVIEW_FIXED_ITEMS_LIST`|GET `/api/v1/global/reviews/{review_id}/fixed-items?page_size=1..50&cursor=...`|每页同上独立重验|200 条目安全投影、文档版本/Evidence ID、签名下一页游标、强 Review ETag、Trace/no-store|游标绑定当前 Session、Review、固定 Version、页大小；错/过期/篡改/跨会话拒绝|

固定版本 `data` 精确含 `review_id/review_round_id/version/review_etag`；`version` 保持原 Capability Version 只读安全字段。条目页 `data` 精确含 `review_id/review_round_id/baseline_version_id/items/next_cursor/has_more/review_etag`，`items` 沿用原 Capability Item 安全投影。GET 不含来源文件正文、Secret 或客户签署，不改变原通用 `/api/v1/global/capability-baselines/...` 可见性。默认应用和 Windows 只读模式不装配；Windows 显式写模式才装配。固定内容 GET 只是可核对材料，不构成决定凭证；决定端仍单独重证资格和来源。
