# DOC-05-A04-P02 版本历史受权下载入口

- 日期：2026-09-29；Phase 2 Platform Core；结果：`FRONTEND_CONTRACT_PASS`。输入为冻结 `DOCUMENT_VERSION_DOWNLOAD`、P01 固定同源路径方法、P02 版本历史界面；决策 `DEC-20260929-483`。
- Changed/Files：`apps/frontend/src/modules/document/views/ProjectDocumentDetailView.vue` 在已读取的 AVAILABLE 版本行添加“下载版本 N”原生链接；对应视图测试验证固定 PROJECT href、新标签安全属性、未加载/空版本没有链接，且页面未自行获取正文。
- 行为/安全：链接请求由浏览器原生发出，后端重新检查 Session、Project、License、文件完整性与并发；`target=_blank`、`rel=noopener noreferrer` 保留详情页以便过期/拒绝时处理。前端不缓存流式文件、不嵌入存储定位；明确提示这不是文内预览/定位。
- Tests：定向视图 10、前端全量 38 文件/841 项 PASS；`pnpm build` 含 typecheck PASS。真实文件下载未运行。
- Migration/API/upgrade：无后端 API/Schema/Migration/权限/依赖变化；兼容冻结 `/api/v1`/DB0049，无升级步骤。
- Known Issues/Next：下一项以隔离真实文件和真实浏览器验证下载流、名称/类型、拒绝与清理；正式信任、Server 2025/Debian 13、性能质量/Gate3/UAT/可用包仍待。
