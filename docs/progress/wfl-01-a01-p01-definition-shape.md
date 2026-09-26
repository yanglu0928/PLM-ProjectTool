# WFL-01-A01-P01：Workflow 定义形状

- Changed：新增不可变版本化 WorkflowDefinition、StageDefinition 和 ChecklistItemDefinition 结构，校验阶段/清单键、正序/唯一、必填标志和 GatePolicy 引用；不提供默认六阶段或清单内容，避免将合理推断当成正式 Gate 配置。
- Files：workflow 领域模块与单元测试、决策日志、状态和版本说明；Migration/公开 API/新依赖：无；版本 `0.1.0.dev0`。
- Tests：Windows 11/Python 3.13 后端 604 项无失败（2 项既有符号链接环境跳过）；有效/非法定义单元测试、开发 wheel 内容检查 PASS，SHA-256 `6a3b91c04a25b66950a7bc04ee9b10ad765c064f7c5fe035fa74d01ebaa559f5`。
- Result：纯领域形状 PASS。未定义正式阶段/Gate 清单、未落库、未接 API 或创建 ProjectWorkflow；WFL-01 整体、Gate 3、可用程序包不标 PASS。
- Next：WFL-01-A01-P02 从 V2.1 六阶段与冻结约束制定版本化业务配置，先记录差异/风险/回滚，再进行单独验收。Windows Server 2025 未运行，Debian 13 按用户指令暂不验证。
