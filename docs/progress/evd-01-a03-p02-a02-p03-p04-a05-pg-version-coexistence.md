# DOCX V1 与 V2 解析结果的数据库共存复验

日期：2026-10-01。WBS：`EVD-01-A03-P02-A02-P03-P04-A05`。结论：`WINDOWS11_ISOLATED_PG18_COEXISTENCE_PASS`。

独立临时 PostgreSQL 18 空库升级至当前 Alembic head 后，对一份纯合成 DOCX 建立同一 DocumentVersion 的两条独立 Job、成功 ParseRecord 与私有 ResultRef：V1 保留段落节点，V2 保留段落并增加内置标题节点。数据库中两条不同 parser_version 的记录均为 SUCCEEDED；Document 所有的固定结果读取 Port 按各自 ID 读回原规范字节，不修改 V1 历史。Evidence 在 V2 结果中证明 SECTION，在 V1 结果中对同位置拒绝。跨项目查询、合成授权撤销及私有 V2 结果字节篡改均失败关闭；V2 结果损坏后，V1 结果仍可独立读取。

验证脚本真实退出 0；自有临时 PostgreSQL 进程停止、目录清理。本项仅新增验证脚本与记录，不改生产代码、公开 API、ORM/Schema、权限、依赖或发行包；Migration 与升级动作均无。生产代码的最近全后端 1,746 项与 wheel 构建是前一 WBS 结果，本项未重复运行。

已知边界：Document 授权使用已检查的合成快照替身，而非正式 Session/License；本项只证明已发布 V1/V2 记录共存，不模拟部署时正在 RUNNING 的 V1 Worker。升级前旧 Worker 静止/排空、正式信任材料、客户文档、Windows Server 2025/Debian 13 与 Gate 3 仍待验。下一项专门核查升级时未收尾作业的安全流程。
