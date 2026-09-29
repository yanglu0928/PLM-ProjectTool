# DOC-05-A05-P06 项目上传 Commit/Abort 安全业务回执

- 日期：2026-09-30；Phase 2 Platform Core；结果：`FRONTEND_CONTRACT_PASS`。输入：冻结 `DOCUMENT_UPLOAD_COMMIT/ABORT`、后端 201/200 合同、P04 已收内容及 P05 私有传输；决策 `DEC-20260930-490`。
- Changed/Files：`apps/frontend/src/modules/document/api/documentUploadFinalizeClient.ts` 显式区分新建/升版 Commit，校验内容回执、目标文档和父强 ETag，绑定 201 的 Upload/Document/Version/Parse Job ID、正整数版本及精确 Location；Abort 严核 200 `ABORTED/cleanup_pending`。两种返回只含白名单 `first_result` 且 `is_current_state_proof=false`；状态/授权/许可/版本/幂等的确定性拒绝与断线、503、伪成功的未知结果分离，不自动重试。
- Tests：首轮定向 42 项有 31 项因新客户端 UUID 正则漏 4 位分组而失败；修正并增补外文档升版回执与 Abort 冲突后，定向 44、前端全量 41 文件/960 项、`pnpm build`（含 typecheck）PASS。真实 PG/浏览器上传、Commit/Parse 未运行。
- Migration/API/Upgrade：无后端 API、Schema、Migration、权限或依赖变化；兼容冻结 `/api/v1` 和 DB `20260927_0049`，无升级步骤。
- Known Issues/Next：首次幂等回执不代表当前文档状态，后续 UI 须独立 GET。下一项 `DOC-05-A05-P07` 做项目上传页面/状态机，再进行 Windows 11 隔离浏览器/PG/真实文件与解析验证；正式信任源、其他平台、Gate 3/程序包仍待。
