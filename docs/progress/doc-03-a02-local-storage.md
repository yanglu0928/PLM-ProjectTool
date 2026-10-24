# DOC-03-A02：受控本地 Storage Adapter

- Phase/WBS：Phase 2 Platform Core / DOC-03-A02。输入：Gate 2 冻结 ADR-008、DM-03、SC-02，DOC-03-A01 与 DEC-20260925-088。编码前检查：Document Infrastructure 内部适配；无新增实体/API/权限入口，调用方须先授权 FileObject；验收为受控路径、完整暂存、同卷无覆盖发布及失败关闭。
- Changed/Files：`local_storage.py` 提供 UUID 派生的 GLOBAL/PROJECT 暂存与正式相对 Locator、独占写入和同卷硬链接发布；`test_local_file_storage.py` 验证拒绝路径穿越、无效 Scope、重解析标志、硬链接源、目标覆盖和 Windows 大小写别名。物理路径不暴露给 HTTP 客户端。
- Migration/API/升级：无新 Migration、公开 API 或依赖；目标数据库仍需按 DOC-03-A01 升至 `0020`。适配器目前未装配到公开服务，停用可不接线；已有临时文件须由后续受控恢复/清理流程处理，不盲删。
- Tests/Result：Windows 11/Python 3.13 后端 448 项无失败，其中 2 项真实符号链接创建因当前账户权限跳过；开发 wheel PASS。内部存储边界在已测范围 PASS，不代表文件/数据库跨资源原子性或上传/下载完成。
- Known Issues：真实 Windows 重解析点/符号链接逃逸端到端未完成；私有存储根的操作系统 ACL 与并发替换防护必须在部署验收检查。硬链接发布后暂存删除或后续数据库提交失败时可能留残余，需状态命令与恢复器；Windows Server 2025/Debian 13 未验证。
- Next：DOC-03-A03 FileObject 内部状态命令与恢复边界前置核查。
