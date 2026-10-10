# DOC-03-A04-A04-P04-P02：上传 Commit 内部原子编排

日期：2026-09-26；版本：`0.1.0.dev0`；状态：内部命令 PASS，公开 Commit/Abort 和 Parser Worker 未完成。

按冻结 API-02、DM-03、ADR-007、`CR-DOC-006` 和 `DEC-20260926-116`，Document 模块新增上传 Commit 内部服务。第一短事务重查许可、Session/CSRF/项目角色/创建者（生产适配时）与 UploadIntent/FileObject/父 Document 状态，只取不可变快照；本地 Storage 在事务外校验 Hash/Size 并同卷无覆盖提升。第二短事务再次授权和核对快照，依次将 FileObject 标为 AVAILABLE，创建新 Document 或给现有 Document 增加不可变版本，更新 UploadIntent 为 COMMITTED，并调用 Job Owner Port 登记 Parse Job/Outbox、追加 Audit 与幂等收据，一起提交。数据库事务失败但最终文件已存在时，仅经匹配 Hash 的 FINAL_VERIFIED/LINKED_PAIR 路径恢复；损坏或不明状态失败关闭。

安全锁序为 Project → 既有 Document → UploadIntent → FileObject；上传创建者的授权读取不预先锁 Intent，事务命令仍在正式锁下复核。对已有 Document 要求父版本，首传与同 Key 重放只生成一个 DocumentVersion/Job。重试请求的新 trace 不覆盖原 Job/Outbox trace。

Windows 11/Python 3.13 后端 502 项无失败（2 项符号链接权限跳过）；隔离 PostgreSQL 18/临时文件验证新建/升版、父版本缺失/冲突、同键重放、创建者/许可拒绝、Audit 失败整库回滚、最终文件恢复与损坏正文拒绝；开发 wheel PASS。无新迁移、公开 API 或依赖，目标库需已有 `0026`。真实 Session/CSRF + License 的 HTTP 组合、Abort、Parser Worker、Server 2025 和发行信任源未验证；不能据此关闭 P04 或 Gate 3。
