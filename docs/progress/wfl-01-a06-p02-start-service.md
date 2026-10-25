# WFL-01-A06-P02：Workflow 启动内部受权命令

2026-10-02 / Phase 2 / `INTERNAL_SERVICE_PASS`。编码前检查：Gate 2、API-02 的 `WORKFLOW_START`、六阶段 V1、0030 Workflow Schema、0015 通用幂等收据、ProjectManager 项目写权限、Session/CSRF、License Guard、Audit 与 P01 原子持久层具备。本项只在 Workflow Application 层完成启动命令；不改冻结 API/Schema/依赖，不挂公开路由，不推进 Stage Gate、Review 或业务清单结果。

实现：先鉴别 Session，再检查 License；写事务内重新鉴别并锁定当前 ProjectManager 资格，预留 actor/project/operation/key 与请求版本指纹，同事务启动 NOT_STARTED/v0→ACTIVE/HANDOVER/v1、写 `WORKFLOW_STARTED` Audit、完成收据并提交。相同 Key/请求仍须重新满足当前权限，从固定六阶段 V1 定义重构**首次**启动响应，而非把后续当前阶段状态作为重放结果；不同请求拒绝，收据根身份或定义事实不符失败关闭。Repository 错误边界移至 Application 独立模块，保持依赖方向。决策见 `DEC-20261002-598`。

验证：新单元8项；后端全量 1824 项通过、3 项既有环境跳过。`validation/wfl-01-a06-p02-start-service/verify.py` 在 Windows 11/一次性 PostgreSQL 18.6 从空库升级至 head 且 Alembic check 无新操作；真实 Session/CSRF、ProjectManager/非经理/外人、合成 License 拒绝、初启/同 Key 重放/版本与请求冲突、Audit 注入失败全回滚、同 Key 双写者只一次启动均通过。脚本退出0，数据库/集群停止并清理；开发 wheel SHA-256 `12b132d3cef3aabb835da1531a02616a43508b4899e1b65b9c7799a91c4f3752`，非发行包。现有计算列 default 提示非本项新迁移。未以合成 License 视为正式信任验收。

兼容/升级/回滚：不增加 Migration、公开 API 或依赖；已有 0015/0030 结构不需迁移。部署前可撤内部服务而不动既有状态；已产生的真实 Workflow/Audit/收据不可静默逆转，只能按后续受控业务流程处理。正式 HTTP、Windows 生产组合、正式 License 来源、首阶段 Gate、Server 2025/Debian、性能/UAT/Gate 3 仍开放。下一项 `WFL-01-A06-P03` 可选 HTTP 命令与合同验证。
