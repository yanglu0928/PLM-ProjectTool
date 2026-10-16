# AI-02-A08-P02：模型内部安全状态命令

日期：2026-10-02；状态：Windows11 隔离 PostgreSQL18.6 内部链 PASS。依据 CR-AI-004/005、DEC-671、Schema0058。

Changed：新增 `AIModelStateService` 与 SQLAlchemy Repository，只允许 AVAILABLE→SUSPENDED、AVAILABLE/SUSPENDED→RETIRED。两次管理员 Session/CSRF 检查夹持 License，写事务锁定模型并核对强版本；状态行、Audit、0058 不可变首次结果及操作隔离幂等收据同事务。重放校验原结果/Audit 归属，返回原状态/ETag，不读当前状态重建。AVAILABLE/质量关联/厂商调用均未开放。

Tests：单元2项；`validation/ai-02-a08-p02-model-state-internal/verify.py` 在隔离 PG18 验证权限/CSRF/License、未找到/非法前态/版本、同 Key 双并发、跨操作 Key 域、暂停后退休仍重放原暂停、唯一 Audit/结果、Audit 故障完整回滚及用户撤权。后端全量2049运行/3跳过；临时 PG 停止。开发 wheel SHA-256 `5f6568b37f37447146be14a5ad65028546b84e116cf23370a68a4ad0311fa546`。

Migration：无，复用0058。API：无公开挂载。兼容与回滚：无新依赖或冻结 API 变化；未投产可撤内部入口，有历史时保留并向前修复。Known Issues：P03/P04 HTTP/平台装配、质量 Owner/AVAILABLE、正式目标账户/Server2025/Debian、Gate3/UAT/可用包未验。Next：`AI-02-A08-P03` 安全可选 `:set-state` HTTP 合同。
