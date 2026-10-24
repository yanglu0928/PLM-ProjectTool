# DOC-05-A03-P01 DocumentVersion 只读前端客户端

- 日期：2026-09-29；Phase 2 Platform Core；结果：`FRONTEND_CONTRACT_PASS`。
- 输入/Trace：冻结 `DOCUMENT_VERSION_LIST/GET`（`docs/api-contract/api-02-platform-security-document-governance-v1-candidate.md`）；现有 Windows 11 合成后端受权版本读取合同；`DEC-20260929-479`。
- Changed/Files：`apps/frontend/src/modules/document/api/documentReadClient.ts` 新增 `listVersions/getVersion` 和安全 `DocumentVersionView`；同目录测试增加成功、GLOBAL/PROJECT 固定路径、游标、错误、畸形数据、私有字段排除等覆盖。未改页面、后端或其他模块。
- Contract/security：固定路径及每页 50，Session 同源请求/no-store/超时；仅接收 AVAILABLE 版本元数据，不投影本地存储定位、正文或下载 URL。服务端仍负责真实 Session、项目范围、License 与版本归属授权；前端验证是补充而非授权替代。
- Tests：定向 Vitest 67 PASS；前端全量 38 文件/835 项 PASS；`pnpm typecheck` 与 `pnpm build` PASS。生产浏览器/PG 针对本客户端未运行。
- Migration/API/upgrade：无 Schema/Migration/依赖/后端 API 变化；兼容冻结 `/api/v1` 与 DB0049，无升级步骤。
- Known Issues/Next：目前无版本历史页面或内容下载入口；正式 License/目标账户信任、Server 2025/Debian 13、性能质量/Gate 3/UAT/可用包待验。下一 WBS 为版本历史 UI，随后独立实际浏览器/PG 验收。
