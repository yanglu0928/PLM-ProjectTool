# DOC-01-A05-P02 内部受权下载来源

- 日期：2026-09-26；状态：内部 Service/Repository PASS；不开放下载 HTTP。
- 基线：冻结 DM-03 DocumentVersion/FileObject 与 API-02 受权下载；决策 `DEC-20260926-129`。
- 实现：同一只读短事务验证当前 Session、License、项目当前成员或 GLOBAL 管理员及父 Document 可见性；Repository 仅联结 AVAILABLE Version 与 PERSISTENT/AVAILABLE、Scope/Project 与 Hash/Size/MIME 一致的 FileObject。`DocumentDownloadSource` 仅内部使用，含文件 ID、Locator/Hash/大小/MIME；敏感 Locator 和 Hash 不进入对象 repr，不存在公开 DTO 转换。
- 验证：Windows 11/Python 3.13 后端 530 项无失败（2 项既有符号链接环境跳过）；隔离 PostgreSQL 18.6 验证真实 Session/项目权限、跨 Document/Project、受限 Version/FileObject、License 拒绝与停用成员即时失权，且 Locator 不出现在 repr；开发 wheel PASS。临时库已删除、测试服务已停止。
- 无 Migration、新依赖或公开 API 变化。来源取出后的实际文件快照、完整性异常事件、发送前状态复核、并发容量和 HTTP 中断清理仍待；本项不证明下载可用。
