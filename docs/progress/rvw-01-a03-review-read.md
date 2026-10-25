# RVW-01-A03 固定 Review 快照内部查询

2026-09-26；版本 0.1.0.dev0；结果 WINDOWS_INTERNAL_QUERY_PASS；来源 CR-RVW-001、Review 持久层设计 V1、RVW-01-A02/0034 与多人纯领域。

## 编码前检查

Phase 2 Platform Core；当前任务只解决内部可信调用方事务查询。前置 0034 隔离 Schema/纯领域已验；涉及 Review、Round、Assignment、Decision、Subject Snapshot/refs/lock、events。无新迁移、HTTP、技术栈/权限/Scope 改变。调用方必须先校验 Session、License、Scope 与主题 Owner 权限；本 Port 不是授权服务，不可直接暴露公开接口。

验收：Scope 精确过滤、固定版本与完整历史不改写、当前身份与历史进度分离、缺固定记录/计数异常拒绝、调用方事务结束前锁有效、查询不写入。风险：全历史读取成本尚未性能验证，真实 Owner/资格尚不存在；历史 APPROVED/ELIGIBLE/ACTIVE 不是业务放行证明。

## Changed / Files

- `apps/backend/src/plm_assistant/modules/review/application/read_snapshot.py`：不可变身份/历史依据/固定轮次 DTO 与查询 Port，精确 UUID/Scope/版本/UTC/32 字节摘要/集合校验。
- `apps/backend/src/plm_assistant/modules/review/infrastructure/read_repository.py`：Core 当前值、不依赖 ORM identity map；Review→Round 共享锁、完整决定与 Assignment/事件/快照/身份锁核对，返回当前 Review 与独立固定轮次。
- `apps/backend/tests/unit/test_review_read_snapshot.py`：8 项单位验收，包含不可变、旧轮次与新身份、Scope/观测/版本/缺快照/异常计数/活动事务拒绝。
- `validation/rvw-01-a03-review-read/verify.py`：随机自建隔离库，结束仅清理自己创建的数据库。

## Tests / Result

Windows 11、Python 3.13、PostgreSQL 18.6。完整后端 **692 项无失败，2 项既有符号链接权限环境跳过**。新查询隔离脚本 PASS：缺身份/跨项目/跨 Scope 返回 None 且不造数据；完整启动与首条 RETURN 保持 IN_REVIEW，完整集合 RETURNED；新轮保持旧版本/意见，部分处理撤回保留 PENDING；来源 Evidence 后来 INELIGIBLE，历史观测仍 ELIGIBLE；显式 GLOBAL 单人完成与 Project 隔离。

读方保持 Review 共享锁时，遵循先锁 Review 的实际 SQL 写方受到 lock_timeout 拒绝；事务结束后新轮启动成功。无调用方事务时不隐式开启事务。缺子快照/异常根计数单位测试拒绝安全错误，未向外暴露数据库详情。

0034 Schema、0033 Gate 固定记录、0032 Checklist/当前查询、0031 历史升级、受权 Workflow 初始化/GET 和 Windows 双显式组合回归全部 PASS。没有重新运行真实客户资格、Review HTTP、覆盖率或性能测试；不声称这些通过。

开发 wheel 构建及打包新查询文件 PASS，SHA-256 `21c0b190980995e3296de7f93bcde2278a73a8ce66ed0869a01b5dae272a0303`。此 wheel 是开发构件，不是可使用的最终安装包。

## Migration / API / Compatibility / Known Issues / Next

无新 Migration/API/依赖/架构调整，需既有 0034；升级无新数据库动作。应用可停用本 Port 回滚，保留不可变历史。锁序保护要求受控写方先获取 Review 锁，未宣称任意直接 SQL 都无死锁。Server 2025 未验、Debian 13 暂不验证，均保留兼容目标。

真实 Subject Owner/当前资格/受权服务/审批命令仍缺，不能把本结果当客户批准、当前来源有效或 Gate 证明。Next：RVW-01-A04 Review Subject Owner/读取授权前置与受权读服务设计；仍持续执行，Gate 3 与完整可用程序包尚未完成。
