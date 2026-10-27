# CR-EXEC-003：仅使用云端沙箱运行项目程序

- 日期：2026-10-27
- 来源：用户明确要求不得在其本机执行任何程序，所有运行使用模拟沙箱，并以尽快交付可验收程序为唯一目标。
- 当前证据：本会话的本机命令执行环境无响应；GitHub 仓库已连接，主分支没有现成的 Actions 状态检查或可复用工作流。
- 冲突/偏差：既有 Windows 11 内部候选包流程依赖本地 Win11/Edge/PostgreSQL 组合。改为云端托管 Runner 自动运行源码测试，不能等同 Windows 11 实机兼容验收。
- 方案：
  1. 停止所有本机程序运行，等待本机环境恢复（不符合持续推进目标）。
  2. 在独立 feature 分支建立 GitHub Actions 云端沙箱测试，并将其结果限定为源码/合同/构建验收（采用）。
- 选择理由：在不访问用户设备、不外传客户数据/Secrets 的前提下恢复可重复的自动执行。只提交仓库源码与测试，不上传本地候选包、用户资料或日志。
- 影响：增加 CI 工作流和记录；不改产品架构、API、数据模型或 Scope。云端测试通过仅说明该 Runner 的测试/构建结果；Win11、Windows Server 2025、Debian 13 的正式兼容结论仍须各自证据。
- 风险：GitHub 托管 Runner 的系统、依赖源和资源与用户设备不同；第三方依赖安装可能失败或消耗较多 CI 时间。
- 迁移/回滚：工作流只对该 feature 分支和指向 main 的 PR 执行；可通过后续提交移除工作流并恢复原执行路径。分支合并前不影响 main。
- 验证计划：由提交触发云端 workflow；检查后端测试、前端测试/typecheck/build 和后端 wheel 构建。任何失败按日志修复；不把未执行步骤报告为 PASS。
- 状态：已记录，待云端工作流执行。


## 云端首次运行偏差（2026-10-27，实施前记录）

- 首次 Actions 运行已证明后端依赖可在 GitHub Ubuntu Runner 安装，但后端全测实际结果为 3,874 tests、9 failures、25 errors、75 skipped；其中 25 项导入错误均因测试依赖组未声明 pytest，另有 Windows launcher/path 相关断言在 Ubuntu 上失败。前端在 setup-node 缓存初始化阶段因 pnpm 尚未安装而失败；后端 wheel 尚未执行。
- 调整：将云端 runner 改为 GitHub 托管的 Windows Server 2025 windows-2025，以匹配 Windows 专属行为的沙箱验收；将 pytest 纳入 test extra；调整前端 pnpm 安装顺序并用后续 PR 运行复验。
- 兼容性说明：Windows Server 2025 是隔离托管 VM，仍非 Windows 11 实机；通过结果只作为云端模拟证据，不等于 Windows 11/Gate/Pilot/发行 PASS。
- 风险/回滚：依赖新增仅属于测试 extra，不进入生产依赖；工作流可在 feature 分支通过后续提交回滚。失败测试必须保留失败并修复，不降低测试范围。

- Windows Server 2025 rerun result: frontend tests/typecheck/build passed. Backend installed dependencies and ran 3,849 tests; one test failed because its input temp path used the 8.3 short username while the service plan correctly emitted the resolved long path. Planned narrow test correction: assert the canonical resolved executable/config paths; preserve all product behavior and assertions on quoting, command shape, and no secret leakage. This remains an unresolved failure until cloud rerun.
