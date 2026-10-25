# DOC-05-A05-P02 项目 UploadIntent 安全业务客户端

- 日期：2026-09-29；Phase 2 Platform Core；结果：`FRONTEND_CONTRACT_PASS`。输入：冻结 `DOCUMENT_UPLOAD_CREATE`、P01 私有 Session 桥接、后端可选 PROJECT 上传意图 201；决策 `DEC-20260929-486`。
- Changed/Files：`apps/frontend/src/modules/document/api/documentUploadIntentClient.ts` 区分新建 Document 和已有文档升版，限制目的/分类/名称/大小/MIME/ID/原幂等键，校验成功 201 的 JSON、trace、Upload ID、43 位 token、未来 UTC 到期、固定 Location、no-store，仅返回白名单内存结果；确定性错误与未知结果分离，不自行重试。对应测试覆盖安全投影、请求体、输入拒绝、权限/License/项目/状态/版本/幂等拒绝、伪响应与断线。
- Tests：首轮定向 31 项中 11 个错误映射用例因夹具把错误放进 `data` 而失败；修为真实顶层 `error` 后定向 31/31、前端全量 39 文件/876 项 PASS，`pnpm build`（含 typecheck）PASS。真实 PG/浏览器上传未运行。
- Migration/API/Upgrade：无后端 API、Schema、Migration、权限或依赖变化；兼容冻结 `/api/v1` 和 DB `20260927_0049`，无升级步骤。
- Known Issues/Next：短时 token 只在调用方内存返回，本项没有内容 PUT、Commit/Abort、页面或解析任务真实证据。下一项 `DOC-05-A05-P03` 做内容 PUT 的受控传输；正式信任源、Server 2025/Debian 13、Gate 3/完整程序包仍待。
