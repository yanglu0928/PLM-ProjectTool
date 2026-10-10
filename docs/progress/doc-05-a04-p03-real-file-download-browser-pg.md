# DOC-05-A04-P03 Windows 11 真实隔离文件下载验收

- 日期：2026-09-29；Phase 2 Platform Core；结果：`WINDOWS_11_SYNTHETIC_BROWSER_REAL_FILE_PASS`。输入为冻结 `DOCUMENT_VERSION_DOWNLOAD`、后端 verified snapshot/流式 GET、P01 地址与 P02 入口；决策 `DEC-20260929-484`。
- Changed/Files：`validation/prj-05-a04-browser-project/serve.py` 增加互斥 `--document-download-api-only` / `--document-download-browser`：每轮随机库及临时 data root，使用正式 LocalFileStorage 发布 50 字节非客户合成文本，建立匹配 SHA-256/大小的 AVAILABLE FileObject 和 DocumentVersion；并核临时文件根移除。`ProjectDocumentDetailView.vue` 将原 `target=_blank` 改成同标签附件链接，测试随之调整；原 P02 已推送历史保留，以本条偏差追溯。
- API/PG：独立模式完整 exit0，下载真实字节及 SHA-256 一致，Content-Length/Content-Disposition `attachment`/`text/plain`/no-store/nosniff 符合合同；匿名 401、外项目 404、Range 400。SQL 有 1 条受权真实文件支撑版本、外项目 0；随机库、角色、Vault、临时文件根清理断言通过。
- Browser：Windows 11 IAB 合成成员进入 OWNED 项目→Document 00→版本历史，版本行显示 `text/plain`/50 字节与“下载版本 1”。首轮新标签下载等待原标签事件 15 秒超时；事后发现新标签实际保存了文件，故该轮仅事件不可观测。改同标签并重建前端后，点击触发原标签下载事件，浏览器保存 50 字节，SHA-256 `72e5df2e4b099d1736bd7031192212402f3b74f56db444a99040f608dc1201d1` 与原文一致，详情页保持；浏览器夹具完整 exit0（2 个 Session）、SQL 与清理通过。两份纯合成下载均送入 Windows 回收站，可恢复；浏览器临时标签的最终关闭调用被中断，标签清理未证实。
- Tests/compatibility/upgrade：`py_compile`、隔离 API/PG、实际 IAB/PG、前端全量 841 项及 typecheck/build PASS。无后端 API/Schema/Migration/权限/依赖变化，兼容 DB0049/冻结 `/api/v1`，无升级步骤；PoC PostgreSQL 原为停止，最终 fast stop 恢复停止。
- Known Issues/Next：同标签方案在会话失效/拒绝时可能导航到服务端错误页，需后续 UX 改善；下载不等于文内定位/预览。正式 License/目标账户信任、Server 2025/Debian 13、性能质量/Gate 3/UAT/可用程序包仍待。
