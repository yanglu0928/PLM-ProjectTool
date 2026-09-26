# DOC-01-A04-P01 DocumentVersion 内部元数据读取

- 日期：2026-09-26；状态：内部 Service/Repository PASS；公开 GET 尚未挂载。
- 基线：冻结 DM-03 DocumentVersion/FileObject、API-02 `DOCUMENT_VERSION_LIST/GET`；决策 `DEC-20260926-124`。
- 实现：同一短事务复用当前 Session、License、PROJECT 当前成员或 GLOBAL 管理员及父 Document 可见性；按 `version_no` 降序 keyset，普通读仅投影 AVAILABLE 版本与 PERSISTENT/AVAILABLE、同 Scope/Project、Hash/Size/MIME 一致的 FileObject。`DocumentVersionView` 含版本身份/序号、摘要、大小、MIME、可用状态、前驱、创建/最近完整性检查时间，不含 FileObject ID、Locator、来源内部元数据或正文。
- 验证：Windows 11/Python 3.13 后端 519 项无失败（2 项既有符号链接环境跳过）；隔离 PostgreSQL 18.6 当前 Schema 上，三版本两页、跨 Document/Project、GLOBAL 管理员、无成员、受限版本/文件、License 拒绝与权限即时变化 PASS；开发 wheel PASS。临时库删除，测试数据库服务停止。
- 无 Migration、新依赖或公开 API 变化；版本 HTTP 需要独立签名页游标、GET 合同及目标账户密钥装配。正式文件物理完整性与受权流式下载未做，本项不能证明文件可下载。
