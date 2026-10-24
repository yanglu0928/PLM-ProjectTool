# SOL-03-A06-P03-A04：当前批准需求全集只读证明

日期：2026-10-24。状态：`INTERNAL_PASS`；本片不修改 Outline 覆盖结论。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前 Phase/WBS | Phase 2 / SOL-03-A06-P03-A04 |
| 输入基线 | Gate 2 冻结 DM-05/API-04；A03 前置复核；现有 Requirement Workflow 完整范围仓储、资格 Owner 与 REQ_VERSION_GET 授权 |
| 前置 | Gate 2 已批准；Requirement 当前版本、正式 Review/来源资格与同事务完整范围锁已实现。A03 称“无项目全集 Port”不准确：`lock_complete_scope` 已存在，但缺可供 Outline 调用的受权、有界只读服务 |
| 涉及模块/实体 | requirement、project、license；Requirement Root/Version、Review/Round、正式状态决定；只读复用 Workflow 资格 Owner |
| 涉及 API/权限 | 不新增公开 API 或 Schema；在调用者事务内验证 Session、License 和 `REQ_VERSION_GET` 项目权限，禁止未经授权直接调用资格 Owner |
| 验收标准 | 输出同一事务中至多 500 个根的当前正式批准版本全集；空集、超限、错误项目/指针/Review/决定、未授权及并发写入均失败关闭；不修改 Outline coverage |
| 风险 | 现有范围仓储先扫描所有根及历史版本，需在项目行锁之后、历史扫描之前设置容量栅栏；完整资格 Owner 对来源时效的要求比单纯指针更严，旧源失效必须失败关闭，不能降级为“已批准”假事实 |

## 设计与回退

复用现有 Requirement Workflow 完整范围仓储和现时资格 Owner，不复制批准指针/Review 判断。为仓储增加可选根数上限（原 Workflow 默认行为不变）；新只读服务在**调用者事务**验证 License/Session/Project 后调用有界 Owner，返回最小固定版本及正式排除决定标识。项目共享锁与 Requirement 写入的项目排它锁互斥；同一事务不暴露分页中间态。上限外直接失败关闭，不截断或假装全集。无迁移或数据改写；若新服务失败，关闭调用入口并保留旧行为。

后续 Outline 必须独立比较全部当前已批准版本与所有现时批准 Section 的 Trace 并集；本片通过不意味着 Outline coverage PASS、Pilot 或 Gate 3 通过。

## 验证记录

- 定向单元 `test_requirement_workflow_qualification.py`：13 通过，涵盖已授权完整库存、先拒绝再读、空范围/错误输入、主体错配、仓储上限配置；同文件既有用例还覆盖 Review/来源/正式决定漂移。
- Windows 11 / PostgreSQL 18.6 隔离实例 `validation/sol-03-a06-p03-a04-approved-requirement-inventory-pg/verify.py` 退出 0：4 个根的全集与 2 个批准版本成功；同范围上限设为 3 时返回不可用而非前三条；项目锁存在；空集不可用；迁移 head 与 ORM drift 无新操作。脚本停止并删除本次自建临时实例/库。`max_roots=500` 的生产候选装配值由服务约束及脚本正常路径共同验证。
- 初次尝试连接旧共享 55434 端口超时，服务未运行；未启动或修改归属不明的旧数据目录，改用本次创建的 ASCII Temp 隔离实例。旧范围夹具缺现今必需的验收条目，脚本只在本次临时库补齐测试行；未更改正式业务规则。
- 现有 Alembic 操作符类/计算列比较警告仍在，`command.check` 返回无新增升级操作。后端全量结果见本次 `STATUS.md` 最新测试记录。

本片没有公开入口、数据库迁移或客户数据外发；正式生产装配仍需后续 Outline 调用者显式注入有界仓储，且只有后续完整覆盖与 Review 测试通过才能改变 Outline 的 `coverage=UNAVAILABLE`。
