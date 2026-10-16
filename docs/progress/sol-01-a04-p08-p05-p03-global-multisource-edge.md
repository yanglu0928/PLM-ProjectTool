# SOL-01-A04-P08-P05-P03：GLOBAL 两固定文档多来源 Edge/PG 组合验证

日期：2026-10-09；结果：`GLOBAL_MULTISOURCE_EDGE_PG_PASS`，限 Windows 11、本轮一次性 PostgreSQL 18.6/pgvector、合成管理员/文档/证据和 Edge 自动交互。脚本勾选只证明程序机制，不代表客户资料已实际脱敏或真人业务确认。

编码前检查：Phase 2；输入 P05-P02-P02 前端合同、CR-SOL-009/010、P04-P03 单来源隔离浏览器夹具和已通过的多来源内部 Owner。前置单来源真实登录/Session/CSRF 与 Confirm/Revoke/回查已验证。本任务仅扩展验证夹具，不改生产代码、Schema/API/权限。验收为两个不同 DocumentVersion/Evidence 的顺序及文件绑定、逐项核查门禁、Confirm/Revoke/原 Key 回查及会话移除关闭。

隔离夹具：在一次性 PG 与私有文件目录中，除原合成 GLOBAL Document/Evidence 外，再写第二份合成 Reference 文件、FileObject、DocumentVersion 和 ELIGIBLE Document 级 Evidence；同一管理员使用真实 scrypt 登录。复用原 Windows 显式组合与前端构建，以独立 Edge 临时 profile 运行，完成后 PG 停机和临时目录清理。两份文件均为测试字节，不含客户资料或真实密钥。

验证路径：从登录→GLOBAL Evidence 列表→多来源候选页，先选第二文档再选第一文档，重新读取两条 Viewer/当前资格。Preview HTTP 200 后，验证两条 DocumentVersion 与两条 Evidence 原文链接均按选择顺序指向各自受权固定 URL；未逐项打开/勾选前 Confirm 禁用。脚本打开四个链接并逐个勾选后 Confirm HTTP 201，请求正文中的两个有序版本/证据 ID 及原 Key 与选择一致；Revoke HTTP 200。再模拟一次已提交但浏览器未确认的同 Key 待核对状态，回查 HTTP 200 展示完成收据及当前 `REVOKED`，人工核对控件完成后本地锁才清除。移除 Session Cookie 后页面不再开放管理员操作。Alembic `check` 无新操作；原单来源 Edge/PG 回归同轮退出 0。

偏差：首轮 Edge 自动脚本在 Vue 更新禁用状态前同一事件循环内连续点击所有勾选框，未发出 Confirm；调整为等待各勾选框启用，并逐个点击/等待状态变更后通过。这是自动化时序问题，未修改产品门禁或服务器来源证明。相同文档多证据的去重分支已由前端单元合同覆盖，本轮真实浏览器仅覆盖两个不同文档。

兼容/升级/回滚：仅验证脚本与通用测试回调新增可选 `actor/scratch/browser_script` 参数；既有夹具默认行为和单来源回归保持。无生产 API、Schema、依赖或数据迁移。可移除本轮验证脚本回滚，不触及确认/Audit/收据历史。正式 License/目标服务账户、Server 2025、20 并发、Gate 3/UAT/发行及真人业务确认未验；Debian 13 按用户指令跳过。GLOBAL Reference Create 仍须单独验证实际确认资格与生产信任源，不因合成 Edge PASS 自动开放。

TraceLink：CR-SOL-009/010 → P04-P03 → P05-P01/P02 → 本 P05-P03 → GLOBAL Create 前置。
