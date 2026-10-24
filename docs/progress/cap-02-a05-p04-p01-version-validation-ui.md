# CAP-02-A05-P04-P01：能力版本当前来源校验入口

日期：2026-10-24；状态：`FRONTEND_VALIDATE_PASS / FORMAL_REVIEW_PATH_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P04-P01`；本片仅解决 DRAFT Version 的管理员 VALIDATE 入口及报告呈现。|
|基线/前置|冻结 `/api/v1/global/capability-baselines/{baseline_id}/versions/{baseline_version_id}:validate`；既有 Capability Version 读取、管理员会话和 License 守卫；P03-P01 已有单条目 DRAFT 入口。|
|模块/接口|前端 Capability + Auth；POST 空正文、私有 CSRF、原幂等号，无 ORM/Migration/后端 API 变更。|
|权限/风险|仅当前 DeploymentAdmin、非强制改密、DRAFT 可操作；后端重新验证权限、来源和证据。未知结果保留原号并要求核对审计，同号重试；不把 VALIDATE 解释为 Review 或批准。|
|验收|严格核对 200/no-store、版本身份/来源指纹/计数/阻断项报告；用户可看见是否阻断送审；定向、全量前端测试和构建通过。|

在能力版本详情新增“当前来源校验”。校验只返回 DRAFT 当前来源和 Evidence 可用性报告，不推进状态。`SOURCE_UNAVAILABLE`、`EVIDENCE_UNAVAILABLE` 显示为阻断项；非管理员及非 DRAFT 不展示按钮。请求不明时会话存储保留原操作号，需要显式确认后同号重试。已知明确失败可清除该记录；回执不可信则失败关闭。

静态核查发现冻结 Capability `:submit-review` 后虽有 GLOBAL Review 持久化内核，却没有 GLOBAL Review 的公开读取/决定 HTTP 路径；因此本片不加入会导致无法完成审批的虚假“批准”按钮。后续 `P04-P02` 送审界面与 `P04-P03` GLOBAL Review 公开路径需分片，涉及冻结 API 增量时先记 Change Request、保留原合同、再进行权限/迁移/回滚与真实 PG 验证。当前批准版本和 HND-05-A02 前置仍未成立。

验证：VALIDATE 客户端 4 项、面板 3 项；前端全量 175 文件、1931/1931，typecheck 与 Vite build 通过。Vite 大 chunk 警告未解决。未做本片真实浏览器、包内 Edge/PG、正式 Review、人为资格确认、正式信任或安装；Gate/Pilot/Release 均未通过。
