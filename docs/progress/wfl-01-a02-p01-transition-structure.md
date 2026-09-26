# WFL-01-A02-P01：Workflow 状态与迁移结构

- Phase：2；编码前检查：冻结 DM-02/API-02 和配置 V1 存在，前置定义/配置 PASS。仅 workflow Domain，实体为状态与阶段定义；无 API/权限/Schema/新依赖变更。
- Changed/Files：`workflow/domain/transition.py`、八项单元测试、STATUS、CHANGELOG、决策日志。本任务只验证结构，不引入未经证明的 Gate 布尔参数或执行状态写入。
- 验收：枚举与冻结状态一致；六阶段 36 对组合只有五对相邻向前合法；非 ACTIVE、未知/动态 key、归档、旧/畸形锁版本拒绝；按定义序列而非 order 数值加一判断相邻。
- Tests：Windows 11/Python 3.13 全量后端 616 项无失败，2 项既有符号链接环境跳过。开发 wheel 包含 transition PASS，SHA-256 `836f1bf4e6f8a3bad717da8da61521ed42e57ad9e677d62e1c4876e27c04fd78`。
- Result：纯领域结构验收 PASS。API、Permission、数据库、实际 Gate 测试未运行；这些运行行为未实现。锁版本与配置版本明确不同。
- Known Issues：当前 stage 必须来自服务器同事务事实；应用层还须验证 Stage/Gate、License、PM 权限、真实 Evidence/Review、成功历史与失败 Audit。结构通过不得当 Gate 放行。最终完成、BLOCKED 恢复及定义迁移尚待独立设计；不能猜测冻结 API 未定义的终点 key。
- Next：WFL-01-A03-P01 持久层及初始化不变量设计/CR 前置。Gate 3 与可用程序包仍未完成；Server 2025 未运行，Debian 13 暂不验证。
