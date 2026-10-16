# DOC-05-A05-P08-A01 Windows 11 隔离网络上传验收

- 日期/结果：2026-09-30；Phase 2；`WINDOWS_11_SYNTHETIC_NETWORK_UPLOAD_PASS`。编码前检查：Gate 2 冻结 `/api/v1`/DB0049，P01～P07 与 Windows 显式写组合已有证据；范围仅 Document 上传验收夹具，涉及 UploadIntent、Document/Version/FileObject、Parse Job、Audit 与下载。决策 `DEC-20260930-492` 先拆网络和浏览器证据。
- 变更：扩展 `validation/prj-05-a04-browser-project/serve.py` 的互斥 `--document-upload-api-only` 模式。每轮随机 PostgreSQL 库/角色、临时数据根和 Vault 测试凭据；测试材料是夹具内两个微型合成 PDF 字节串，没有客户文件、密钥或正式信任材料。
- 验证：Windows 11 本机 PostgreSQL 18.6 原为停止，用原数据目录及 `127.0.0.1:55432` 启动；`py_compile`/依赖导入 PASS，独立网络夹具 exit0。真实 loopback HTTP 的 Content-Length、SHA-256、检测 MIME、UploadIntent→内容→新建 Commit、同 Key 重放、原 Document 强 ETag 升版 Commit、两版受权下载字节及不同 Key 409 均通过；Abort 重放、匿名401、无 CSRF403、外项目/非成员404 通过。SQL 核两版 AVAILABLE FileObject 与磁盘正文完全相同、两个 `DOCUMENT_PARSE` 入队 Job、2 Commit/1 Abort Audit、Abort 状态及外项目零版本。夹具确认 2 Project/2 Session/1 Active Member，临时库/角色/Vault/文件根清理，事后库 catalog 残留 0。
- 兼容/升级/回滚：无生产程序、API、Schema/Migration、权限或依赖变更；兼容冻结契约与 DB0049，无升级步骤。仅撤此测试模式即可回滚，不触碰正式数据。PoC PostgreSQL 验收后恢复到原停止状态。
- 已知限制/下一步：HTTPX 客户端不等于实际浏览器；P08-A02 需页面操作、浏览器原生 Content-Length、Web Crypto/内存及完整清理。这里只证明 Parse Job 入队，未证明 Parser Worker 消费；正式信任源、Server 2025/Debian 13、性能、Gate 3 和可用程序包均未通过。
