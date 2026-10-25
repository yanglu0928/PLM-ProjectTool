# DOC-03-A04-A03-P03-A02-P03-P01 单候选 TTL 清理

日期：2026-09-26。追溯：冻结 DM-03 崩溃恢复矩阵、数据保留 R7-TEMP 七天、ADR-008、DEC-20260926-107。结果：内部单候选合成验证 PASS；全量扫描、调度和中断补记未完成。

维护调用显式指定 Scope/Project/UploadId 并经授权端口校验。只针对有 UploadIntent、未关联 FileObject、状态为 CREATED/ABORTED/EXPIRED、Token 已失效、创建及文件修改时间均早于至少七天的候选。受控 Locator 的普通单链接文件必须能取得上传共用的 OS 锁；清理请求 Audit 和确定性幂等收据先在 PostgreSQL 提交。随后重新锁定并核对 device/inode、大小和 mtime，释放 Windows 文件句柄后再做最终身份复核和删除，最后追加完成 Audit。不扫描、删除任何正式文件或未知路径。重试不重复请求 Audit；文件已不存在时返回无操作。

Windows 11/Python 3.13 后端 475 项无失败（2 项符号链接权限跳过）；PostgreSQL 18 隔离临时库/合成文件验证合法过期清理、维护权限拒绝、Audit 失败回滚不删文件、活动锁、未满七天、已登记 FileObject 拒绝及审计/收据数量；本地文件测试验证年龄、内容变化与同路径不同 inode 均不删除；开发 wheel PASS。无 Migration、公开 API 或依赖。测试中仅删除隔离临时目录中的合成文件，不触碰客户资料。

已知窗口：完成 Audit 若在物理删除后提交失败，请求 Audit/收据仍存在，但完成事件需后续对账；Windows 文件锁释放与 unlink 之间依赖私有存储根权限及最终身份复核，仍须在 Server 2025 验证。下一子项 P03-P02 负责受控目录扫描与中断对账，再接正式 Session/License/CSRF/Project Role、HTTP、Commit/Abort、Parser Job/Outbox。Debian 13 依用户指令暂不验证，Gate 3 和最终可用程序包未完成。
