# WFL-01-A03-P05：既有项目受权初始化

- Phase 2；输入冻结 DM-02/API-02 ProjectManager Workflow 管理权限、CR-WFL-001/002。前置真实 Session/CSRF/Project 授权与内部初始化 PASS；编码前限定内部命令，无公开初始化 API 或自动回填。
- Changed/Files：新增 `workflow/application/initialize_existing.py`、Project 权限 `WORKFLOW_START`（PM/write）、单元/权限矩阵测试和隔离验证。权限引用只是初始化准备的受权条件，不执行 start，也不冒充冻结 HTTP WORKFLOW_START 的完整实现。
- 行为：先认证，再要求有效 License；写事务重新校验 Session/CSRF 与锁定项目/成员/部门事实、精确 PM proof；同事务初始化与 Audit，显式提交。无 Project 正文/内部表读取，无 bulk backfill；拒绝归档/跨项目/非成员/非 PM。初始化不重置已有实例。
- Tests：Windows 11/Python 3.13 全量后端 630 项无失败（2 项既有符号链接环境跳过）。隔离 PostgreSQL 18.6 真实 Session/Project/CSRF/PM、IM/客户/另一项目 PM/无项目身份 DeploymentAdmin 拒绝、归档与撤销 Session 拒绝、合成 License 过期拒绝、并发唯一/Audit 失败回滚、初态仍 NOT_STARTED/十二 PENDING PASS。矩阵精确增加至 15 项，未放宽角色。
- 测试修复：撤销 Session 的合成 fixture 起初遗漏 lock_version+1，被既有数据库 Guard 正确拒绝；补齐合法测试更新后重跑，不修改生产 Session 规则。
- Build：开发 wheel 包含内部命令 PASS；SHA-256 `39351604b11b151dc22834f5b72063ee117c8b9e1e235838edbcc1a9abed4959`。无 Migration/公开 API/外部依赖变化，升级无动作。
- Result：内部受权初始化范围 PASS。正式 License 供给/发行环境、HTTP、CLI、项目 Workflow start/transition 和真实 Gate 尚未验；未运行生产回填，未生成客户事实。Server 2025 未运行，Debian 13 暂不验证。
- 清理：隔离脚本删除自建随机库，测试数据库服务已停止；没有生产数据库/客户数据操作。
- Next：WFL-01-A04-P01 Workflow 固定实例只读投影与项目授权查询；后续才装配冻结 GET/启动/Gate/历史路径。最终可用程序包仍待完整集成/安装/UAT。
