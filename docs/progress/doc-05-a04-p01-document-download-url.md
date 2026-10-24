# DOC-05-A04-P01 DocumentVersion 受权下载固定地址

- 日期：2026-09-29；Phase 2 Platform Core；结果：`FRONTEND_CONTRACT_PASS`。输入为冻结 `DOCUMENT_VERSION_DOWNLOAD`、现有后端受权流式 GET 和版本历史客户端/UI；决策 `DEC-20260929-482`。
- Changed/Files：`apps/frontend/src/modules/document/api/documentReadClient.ts` 新增 `contentUrl`；同目录测试覆盖 PROJECT/GLOBAL 固定路径、非法 Scope/Document/Version ID 本地拒绝及零网络副作用。
- 安全/性能边界：URL 只含固定同源路径和 UUID，不含 Session token、查询参数或存储定位；实际请求仍由后端 Session/Project/License/文件完整性与并发上限保护。采用浏览器原生附件下载方向，不在前端将最多 100MB 流式响应整包缓存成 Blob。
- Tests：定向 69、前端全量 38 文件/841 项 PASS；`pnpm build` 含 typecheck PASS。尚未接 UI，也未测试真实文件浏览器下载。
- Migration/API/upgrade：无后端 API/Schema/Migration/权限/依赖变化，兼容冻结 `/api/v1`/DB0049，无升级步骤。
- Known Issues/Next：下一 WBS 在受权版本行提供明确下载入口并测试；随后用隔离真实文件验证流式下载/失败边界。此下载入口不等同于文内定位/预览，后者须在 Viewer/Evidence 合同中独立实现。
