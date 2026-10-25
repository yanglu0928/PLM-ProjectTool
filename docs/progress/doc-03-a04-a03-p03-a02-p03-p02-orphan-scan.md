# DOC-03-A04-A03-P03-A02-P03-P02 受控暂存扫描与缺失对账

日期：2026-09-26。追溯：冻结 DM-03 恢复矩阵、R7-TEMP、ADR-008、DEC-20260926-108。结果：内部显式维护批处理合成 PASS；生产调度和正式授权装配未完成。

Storage Adapter 只读遍历 `temp/global/objects/{prefix}/{uuid}` 与 `temp/projects/{project_uuid}/objects/{prefix}/{uuid}` 固定结构，限定条目/候选数量；只返回普通单链接且完整匹配固定 Locator 的候选。异常入口目录失败关闭，未知条目计数并保留，不跟随符号链接/重解析点。批处理逐候选调用 P03-P01，缺 Intent、未满七天、活动写入或已有 FileObject 等均不删除。物理文件不存在但 PostgreSQL 有已提交清理请求、没有完成事件时，重新授权并查数据库/文件后只追加 `DOCUMENT_ORPHAN_CLEANUP_ABSENT`，说明观察到缺失，不伪称本轮删除成功；Audit 已有终态时不重复补记。

Windows 11/Python 3.13 后端 476 项无失败（2 项符号链接权限跳过）；PostgreSQL 18 独立临时库/合成目录验证批量清理、未满足条件保留、请求审计后完成审计失败的缺失对账、重复运行无重复补记，开发 wheel PASS。无 Migration、公开 API 或新依赖；测试只使用临时合成文件。

现仅内部显式维护入口，无生产定时调度、正式管理授权/License 组合或多目标 OS 验证。无 UploadIntent 的未知文件不会自动删除，应在运维巡检中保留并人工调查；本项不扩大为任意路径清理。下一项是正式 Document 上传权限适配与可选 HTTP 组合，然后 Commit/Abort、Parser Job/Outbox。Gate 3、最终程序包仍未完成。
