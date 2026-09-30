# DOC-05-A06-P01 固定版本 ParseRecord 只读客户端

- 日期/结果：2026-09-30；Phase 2；`FRONTEND_CONTRACT_PASS`。编码前检查：Gate 2 冻结 `DOCUMENT_PARSE_LIST`，DOC-04-A05 后端 Windows 显式组合与 DocumentReadClient 固定 Scope/ID GET 已有证据。P08-A02 浏览器上传待确认，但本项只读解析状态，不依赖它；决策 `DEC-20260930-494`。
- Changed/Files：扩展 `apps/frontend/src/modules/document/api/documentReadClient.ts` 的 `listParses`，新增 `documentParseReadClient.spec.ts`。PROJECT/GLOBAL 固定路径、Document/Version ID、独立最长 1024 字符签名游标、50 条分页及安全状态投影；不带 Token、文件路径、解析正文、结果文件或 Evidence。客户端验证状态/时间/Job/结果/错误码形状及重复/畸形页，错误仅映射安全码。
- Tests：首轮前端 43 文件/1006 项测试通过，随后 typecheck 因新测试夹具 `toString` 缺返回类型失败；标注后 `pnpm typecheck`、`pnpm build`（含二次 typecheck）、前端全量 43 文件/1006 项均 exit0。无后端或数据库运行验收，本项不宣称实际 Parser/OCR Worker 成功。
- 兼容/升级/回滚：兼容冻结 `/api/v1`、DB0049；无 ORM/Migration、后端 API、权限、依赖或升级变化。撤客户端方法/测试可回滚，现有读取功能不变。
- Known Issues/Next：前端页面未接入，实际浏览器/PG Parse 列表需另验；服务器 `PENDING` 或上传回执的 Parse Job 只表示入队，不表示处理或证据可用。P08-A02 浏览器上传仍 `INCOMPLETE`，正式信任/Server 2025/Debian 13、Phase3 Worker、精确 Evidence Locator、Gate3/可用包仍待。下一项 `DOC-05-A06-P02` 可把固定版本解析状态安全展示在文档详情。
