# SOL-01-A04-P09-P05-P01：GLOBAL Reference 前端接入核查

日期：2026-10-09。结论：`GLOBAL_REFERENCE_FRONTEND_PRECHECK_PASS`；仅对账前端边界，不代表客户端/页面/浏览器已完成。

编码前检查：Phase 2；输入为 Gate 2 API-04、P09-P02 Owner、P09-P03 GET、P09-P04 List。现有 PROJECT `ReferenceReadClient`、列表/详情页显式 `scope:"PROJECT"` 与 ProjectId 成员身份，不可复用其授权或解析器来读取 GLOBAL。GLOBAL Create 成功页仅显示 ID，尚不能导航到已创建对象；后台列表也未接入。当前 SessionView 有 `deployment_role:"DEPLOYMENT_ADMIN"` 和改密门禁；后端仍强制 Session/License/Admin，前端只做可见性优化。

实施拆分：P05-P02 新建严格 GLOBAL 只读客户端，校验固定 Scope、null ProjectId、ETag、有序来源、签名游标外形与 API 错误 Envelope，不触碰 PROJECT 客户端；P05-P03 后台候选/详情页及 Create 成功后导航，原文下载使用已有受权 `/api/v1/global/documents/{id}/versions/{version}/content`，证据位置使用现有 GLOBAL Evidence Viewer；P05-P04 执行前端回归及 Windows 11 Edge/隔离 PG 端到端。若浏览器无法实际打开内容，不把纯路由点击称为原文定位通过。

安全/兼容：GLOBAL 历史 Reference 读取不等于当前来源资格、确认仍有效或正式方案批准。页面不自动重复不确定 Create 请求，不用 Reference 名称推断原幂等结果。无 Schema/API/依赖变化；回滚移除新客户端/路由/导航，既有 Create/历史保留。正式客户确认、目标账户信任源、Server 2025、20 并发、Gate 3/UAT/发行继续未验。
