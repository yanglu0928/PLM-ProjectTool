# SOL-01-A04-P09-P05-P03：GLOBAL Reference 后台候选/详情与创建后导航

日期：2026-10-09；结果：`GLOBAL_REFERENCE_FRONTEND_VIEWS_PASS`，限定前端合同/构建，不等于真实 Edge/PG 下载和定位验收。

编码前检查：Phase 2；输入 Gate 2 API-04、P09-P02～P04 后端、P05-P01/DEC-1121 与 P05-P02 客户端。只改 Solution 前端页/路由及已有 GLOBAL 入口链接；无 Schema、API 或服务端权限变化。当前 DeploymentAdmin/改密门禁只控制 UI，真正读取仍由后端 Session/License/Admin 校验。

实现：新增 `/admin/reference-solutions` 候选与 `/:referenceId` 详情。候选使用 GLOBAL 专用客户端及有界分页，详情展示历史固定 DocumentVersion/Evidence ID；文档原文链接指向现有受权 GLOBAL 版本下载，证据点击后才调用 GLOBAL Evidence Viewer 返回定位/受权内容链接。多/单来源 Create 成功后展示详情导航，不从名称猜测不确定的首次写入结果；来源候选和证据页也可进入全局候选。文案明确历史读取不代表脱敏确认仍有效、来源现时合格或正式方案批准。

验证：定向页面/已有 Create 页面16项和后续非 Admin/异常负例；前端全量109文件/1647项、typecheck/build通过。Vite 既有主包大于500kB提示保留。未跑 Edge/真实网络；文档下载和 Evidence Viewer 受权重验还需 P05-P04 验证。浏览器内精确原文高亮未实现，当前仅提供位置说明和原文下载。

兼容/迁移/回滚：无 Breaking Change、数据库/依赖/数据迁移；移除新增前端路由与入口可回滚，既有 Reference/确认/Audit 保留。正式客户确认、目标账户密钥/License、Server 2025、20 并发、Gate 3/UAT/发行未验；Debian 13 按用户指令跳过。

TraceLink：API-04 → P09-P01～P04 → P05-P01/DEC-1121 → P05-P02 → 本 P05-P03 → P05-P04 Edge/PG。
