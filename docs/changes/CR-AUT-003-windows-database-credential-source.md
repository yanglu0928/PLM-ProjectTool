# CR-AUT-003：Windows 数据库凭据生产来源

日期：2026-09-25；状态：ACCEPTED_UNDER_CONTINUOUS_AUTHORIZATION；关联：CR-AUT-002、AUT-03-A07-P02。

## 冲突与证据

冻结安全边界要求生产登录的数据库连接不可依赖测试 URL 或明文配置。现有 `create_database_runtime()` 只接受外部提供的 URL；BootstrapSettings 禁止 Secret，交互式初始管理员入口仅为一次性操作。长期运行的 Windows 11/Server 2025 服务尚无凭据来源，故不能开放登录。微软 [CREDENTIALW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/ns-wincred-credentialw) 规定 Generic Credential 可持久保存应用定义的数据，`CRED_PERSIST_LOCAL_MACHINE` 对同一账户在同机后续登录会话可见；它不是跨账户/跨机器自动可恢复的交付包。

## 方案比较与选择

- A：把完整数据库 URL 放普通 YAML/环境变量。拒绝；明文配置泄漏面过大，与既有 Bootstrap Secret 边界冲突。
- B：当前运行账户的 Windows Credential Manager Generic Credential，部署时在本机终端无回显写入，服务启动时按固定 Target 读取。选择 B；凭据不纳入仓库、安装包、普通配置或命令行参数。
- C：外部企业 Secret Vault。可作为后续部署变体，但当前没有指定产品或运行环境，不能假设可用。

## 差异、风险、迁移和回滚

仅为 Windows 11/Server 2025 增加基础设施适配和部署步骤，不修改冻结 API、Schema 或权限。Credential Manager 项目绑定 Windows 登录账户；服务必须以配置凭据的同一账户运行。账户丢失、系统重装、Vault 损坏或数据库密码轮换后须由部署管理员从独立管理的数据库凭据重新录入；不能把 Vault 条目本身当作跨机器备份。Python/SQLAlchemy 运行期会持有 URL，不能声称内存绝对清零。读取失败必须拒绝生产装配且不回显 URL/密码。Linux 仍是正式兼容目标，但需单独安全来源；Debian 13 按用户指令暂不验证，不把 Windows 结果外推。

无数据库 Migration。回滚为停止服务并移除此适配入口；已有 Vault 凭据不会被程序自动删除，部署者需通过系统凭据管理手工移除或轮换。不可自动删除生产凭据。

## 验证计划

Windows 11 使用唯一合成测试 Target 写入、读取、覆盖并仅删除测试 Target；缺失/畸形/非 Windows 路径失败关闭，错误不泄密；检查现有后端回归和 wheel 构建。Windows Server 2025 需实际部署验证后才能记 PASS；账户绑定和恢复演练在 Release Gate 关闭。未满足时 AUT-03-A07 与 Gate 3 保持未通过。
