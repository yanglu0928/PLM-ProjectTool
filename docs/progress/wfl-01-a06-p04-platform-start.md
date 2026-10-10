# WFL-01-A06-P04：Windows 显式平台 Workflow 启动组合

2026-10-02 / Phase 2 / `WINDOWS_COMPOSITION_PASS`。编码前检查：Gate 2 冻结 `WORKFLOW_START`、P01事务写、P02受权命令、P03可选HTTP和现有 Windows `--platform`/`--platform-write` 可信组合具备。本项只在两种显式平台模式装配启动路由；默认与仅登录模式保持关闭，不变更 Schema/API合同/依赖，不判定 Stage Gate。

实现：复用当前数据库 UnitOfWork、Session/CSRF、ProjectManager 写授权、License Guard、Workflow 读/启动 Repository、持久收据和 Audit Service；任何生产信任源缺失仍使平台组合启动失败关闭。无隐式初始化或后台自动启动。历史 `WFL-01-A03-P05` 验证脚本的启动路径404预期随路由演进调整为无CSRF 403；保留默认/仅登录404和 Transition 404，不改旧初始业务事实。

验证：`validation/wfl-01-a06-p04-platform-start/verify.py` 在 Windows 11 一次性 PostgreSQL18.6/真实 Session 下对默认404、login-only404、platform/read-write首次/重放200、非经理404、合成License403、新Key旧版本409、缺License/Secret cursor信任源工厂拒启、每项目唯一启动Audit及收据进行了验证；空库到head的Alembic check无新操作，进程/临时库清理。第一次运行验证脚本因局部变量覆盖数据库名失败，修复脚本后完整重跑通过，无产品数据影响。`WFL-01-A03-P05` 旧矩阵重新跑通并保持未授权/归档/撤权拒绝。后端全量1830项通过/3项既有环境跳过，开发 wheel SHA-256 `b1c628cedd61b4a6b1f0b4f70deeaa125b44ecf45c69f58906c1f805ebacfea7`，非发行包。合成License不等于正式信任。

兼容/升级/回滚：没有新 Migration/依赖/破坏性 API；已具0015/0030即可装配。停用显式平台路由可恢复关闭，但已启动的 Workflow/Audit/收据不应逆转。正式工作台公钥/License、目标账户凭据及 Secret、真实浏览器、Server2025/Debian、首阶段Gate、性能/UAT/Gate3仍未验；当前 Windows 非发行 ZIP 尚未包含本轮代码。下一项按 `STATUS.md` 回到 Workflow 待办/Stage Gate 或其他独立 Phase2 任务。
