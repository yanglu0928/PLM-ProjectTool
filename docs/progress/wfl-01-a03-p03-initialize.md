# WFL-01-A03-P03：内部事务初始化

- Phase 2；前置四表/0030 PASS。输入 CR-WFL-001/002 固定 V1；仅 workflow Application/Repository/Audit 协作，不改 Project 内部表，不新增公开 API、权限、Schema 或依赖。
- Changed/Files：`workflow/application/initialize.py`、`infrastructure/initialize_repository.py`、四项单元测试及隔离 PostgreSQL 验证脚本。调用方持有事务并负责真实 Project 操作授权/License，服务不自行提交，不允许直接绑定用户请求/回填命令。
- 行为：唯一 project_id 的 insert-on-conflict 收敛；新实例一次写全六 Stage、六 Checklist、十二 PENDING Item、NOT_STARTED Workflow，追加 WORKFLOW_INITIALIZED Audit。重试返回原 WorkflowId，不重复审计或重置状态；定义不一致失败关闭。
- Tests：Windows 11/Python 3.13 后端 623 项无失败（2 项既有符号链接环境跳过）。隔离 PostgreSQL 18.6 顺序重试/两请求并发同实例同一次 Audit、全部初始 PENDING、Audit 故障/延迟提交故障/不提交回滚、已有 ACTIVE 进度重试保持原指针与锁 PASS。
- Build：开发 wheel 包含初始化入口/Repository PASS，SHA-256 `0a03ddd37c544d554bf0f30486bf0b537d357c7cede3f129c721f449eed455bf`。Migration/API/新依赖：无；升级无需额外动作。
- Result：内部调用方事务初始化范围 PASS；测试使用合成内部调用方，**不证明真实 PM/Admin/License 权限、生产初始化或 Project 创建接线**。这些尚未实施；无 Workflow 写 API。
- Known Issues：Project 创建事务未调用入口，既有 Project 未授权回填；Gate/Checklist 历史/成功迁移历史/失败 Audit/最终完成 API 等仍待。初始化 Audit 不代表 Workflow 已启动或客户确认。Server 2025 未运行，Debian 13 暂不验证。
- 清理：仅删除脚本自建随机临时库，测试 PostgreSQL 服务已停止；未处理生产或客户数据。
- Next：WFL-01-A03-P04 ProjectCreateService 公共初始化 Port 与 Windows 显式组合接线，真实 Session/Admin/License/幂等/Audit 回滚验证；既有项目受权初始化另任务。
