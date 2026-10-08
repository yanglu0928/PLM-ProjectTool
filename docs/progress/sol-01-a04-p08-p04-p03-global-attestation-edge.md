# SOL-01-A04-P08-P04-P03：GLOBAL 单来源人工核查 Edge/PG 组合验证

日期：2026-10-09。结果：`GLOBAL_ATTESTATION_EDGE_PG_PASS`，限 Windows 11、本轮一次性 PostgreSQL 18.6/pgvector、合成管理员/文件/证据及 Edge 自动交互。自动脚本的勾选与提交仅证明程序链路，不是客户资料已脱敏或真人业务确认。

编码前检查：Phase 2；前置 P04-P02 合同/回查、P03-P05 Windows 显式写组合、隔离真实来源夹具已通过。本任务只检验单条 GLOBAL Evidence/单个 DocumentVersion 的可达性及故障恢复。范围包括登录、Evidence List/Viewer、当前资格、固定原文、Preview、Confirm、Revoke、原操作号回查和 Session 移除后的关闭。未增加默认开放路由或后台自动确认。

执行与偏差：首次夹具仅用 GET 恢复会话，私有 CSRF 按设计不恢复，预览在浏览器内被拒。改用合成 scrypt 凭据、真实登录和 SPA 导航；既有一次性 PG 夹具新增可选凭据参数，默认行为保持不变。真实 Edge 随后发现两个前端兼容问题：资格 GET 和 GLOBAL 脱敏 POST 将浏览器原生 `fetch` 作为类方法调用，导致 Edge 的 receiver 错误，请求未发出；已改为脱离实例调用并加 receiver 回归。另发现 Confirm 成功 201 后，数据库 UTC 微秒格式与浏览器毫秒格式文本不一致，被前端误判为不确定；改为验证双方均为合法 UTC 时刻且毫秒时间值相同，拒绝不同到期时刻。浏览器夹具在 SPA 导航后等待回查按钮可用，避免在 Viewer 尚在加载时点击禁用控件。这些是现有实现缺陷及测试夹具调整，未修改冻结 API/Schema/授权粒度；记录于 `DEC-20261009-1119`。

验收证据：Edge 自动完成真实登录、GLOBAL Evidence 两条列表、选定 Document 级 Viewer/资格读取、预览前不显示已核查原文、预览返回与当前固定版本一致、两条固定原文链接、显式勾选、Confirm HTTP 201、Revoke HTTP 200。脚本以同一管理员和原 Confirm Key 模拟一次不确定结果后的本地待核对状态，回查已完成收据并展示现时 `REVOKED`，核对后才清除本地锁；删除 Cookie 后刷新显示需要当前管理员。一次性 PG/文件夹具在测试结束后关闭清理，Alembic `check` 无新操作。前端全量 `105 files / 1625 tests`、typecheck/build 通过；已有主包大于 500kB 警告。后端生产代码未变，既有全量 `3337 passed / 3 skipped / 4930 subtests` 为前序证据，本项未重跑。

兼容与升级：无 Schema、Migration、API URL、权限或依赖变化，无数据升级。回滚可撤本次前端兼容修复与验证夹具，但不应恢复 Edge 下错误的 `fetch` receiver 或误判成功收据；原确认/Audit/撤回历史继续保留。限制：仅单来源自动化，未验证真人逐项阅读、实际资料脱敏、正式 License/目标服务账户、Server 2025、20 并发、Gate 3/UAT/发行；Debian 13 按用户指令跳过。下一步评估多来源核查入口及 GLOBAL Reference Create 前置，保持真实人工确认边界。

TraceLink：CR-SOL-009 → P03-P05 → CR-SOL-010/P04-P02 → P04-P03 Edge/PG → 后续多来源/创建资格。
