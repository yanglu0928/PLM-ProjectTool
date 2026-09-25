# DOC-02-A02-P01 上传来源 DocumentVersion 内部提交

日期：2026-09-25。版本：`0.1.0.dev0`。状态：内部子任务合成验证 PASS；DOC-02-A02 整体未关闭。

内部命令仅接受已授权、ACTIVE Document/Project 和同 Scope/Project 的 PERSISTENT+AVAILABLE FileObject。文件必须使用 UUID 派生的正式 Locator、DB SHA-256/Size/MIME，且尚未被其他版本引用；按上限流式复验物理字节。提交事务按 Project→Document→FileObject 行锁，重核预期 Document 版本与文件快照；生成连续 version_no/同文档前驱，追加不可变 DocumentVersion 与 UPLOAD 来源引用，更新 latest 指针，并与 Audit/幂等收据一起提交。effective 指针保持原值，不能因上传自动升级为正式业务事实。

Windows 11/Python 3.13 后端 462 项无失败（2 项符号链接场景因账户权限跳过）；PostgreSQL 18 临时库与合成文件的首版/后续版、并发同 Key 重放、跨项目/同文件重复引用、摘要损坏、项目归档和审计失败回滚 PASS；开发 wheel PASS。无新 Migration、公开 API 或依赖，目标库仍需既有 `20260925_0022`。

当前仅合成授权 Port；公开上传、正式 Document 权限、生成/转换/迁移来源、Parser Job/Outbox、effective 确认、真实文件 ACL/备份恢复及 Server 2025/Debian 13 未完成。文件系统与 DB 不具备原子提交；版本提交前做实际字节校验，但无法以此取代部署目录不可变权限和后续完整性巡检。无公开路由挂载，不能作为最终程序包交付。

追溯：`DEC-20260925-098`、ADR-008、冻结 DM-03、`CR-DOC-003`、`validation/doc-02-a02-p01-upload-version-commit/verify.py`。
