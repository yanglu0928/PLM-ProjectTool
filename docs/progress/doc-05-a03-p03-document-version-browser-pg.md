# DOC-05-A03-P03 DocumentVersion Windows 11 浏览器/PG 验收

- 日期：2026-09-29；Phase 2 Platform Core；结果：`WINDOWS_11_SYNTHETIC_BROWSER_PG_PASS`。输入为冻结版本读取 API、P01 客户端/P02 页面及现有随机库浏览器夹具；决策 `DEC-20260929-481`。
- Changed/Files：`validation/prj-05-a04-browser-project/serve.py` 增加互斥 `--document-version-api-only` / `--document-version-browser` 模式；给 51 条合成受权 Document 各建一条 `AVAILABLE` 版本及匹配 FileObject 元数据；实际文件内容没有创建，不测试下载。无生产代码、API、Schema/Migration、权限或依赖变化，撤模式可回滚。
- API/PG：独立模式完整 exit0；匿名 401、外项目 404，受权版本列表/详情均返回 AVAILABLE 安全元数据且不含 locator；SQL 证实 OWNED 51 条匹配的版本/FileObject，FOREIGN 0；随机库、角色、临时 Vault 清理断言通过。
- Browser：Windows 11 应用内浏览器以合成项目成员登录，由“我的项目”→OWNED 项目→项目文档历史→首条 Document 详情→“查看版本历史”，显示版本 1、`application/pdf`、7 字节；展开完整性元数据能看到版本引用与合成 SHA-256。刷新详情后版本列表清空，再次按需加载成功。浏览器未保存截图；完整夹具 exit0、SQL/清理复验通过；PoC PostgreSQL 最终 fast stop 恢复原停止。
- 修复过程：首轮 SHA-256 用字符串入库触发 `ck_doc_file_objects__sha256`，改为 32 字节；第二轮 API 通过但会话计数沿用历史模式断言失败，改为本模式 1 Session。两轮失败不计 PASS；修正后 API/PG 与浏览器/PG 各完整 exit0。`py_compile` PASS。
- Compatibility/upgrade/known issues：兼容 DB0049/冻结 `/api/v1`，无升级步骤。此项只验证合成数据库元数据可见性，不证明真实文件、下载、正式 License/目标账户信任、Server 2025/Debian 13、性能质量、Gate3/UAT/可用程序包。下一项按 WBS 推进受权文件下载前端入口与真实文件验证。
