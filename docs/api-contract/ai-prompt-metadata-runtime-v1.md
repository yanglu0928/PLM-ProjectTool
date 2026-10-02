# AI_PROMPT_LIST/GET 运行时补充（非冻结合同改写）

版本：0.1.0.dev0；日期：2026-10-02；依据冻结 API-03、DM-04、DEC-695/696。

`GET /api/v1/admin/ai/prompt-templates`：DeploymentAdmin Session、可信 Host、有效 License；仅接受 `page_size`（1～200，默认50）和 `cursor`，重复/未知参数拒绝。专属 HMAC cursor 绑定 Session、页大小、位置；返回 `items`、`next_cursor`、`has_more` 和 `trace_id`，不缓存。

`GET /api/v1/admin/ai/prompt-templates/{prompt_template_id}`：同样权限，无查询参数；返回安全元数据与强 ETag。两接口的元数据仅含模板 ID、任务类型、状态、当前活动版本及其 schema/policy refs、内容 hash、ETag。DRAFT/RETIRED 的活动版本字段全部为 null；RETIRED 旧指针仅留内部历史。绝不返回 system/user 模板正文、Secret 或客户数据。

本项为可选 Router，默认应用与当前 Windows 生产组合未挂载，仍返回404。Win11 隔离PG18/合成 License及真实 Session 核查通过；正式游标密钥来源、发行信任、目标账户、Server2025/Debian、生产迁移、Gate3/UAT/可用包另验。Router 存在不代表生产可用。
