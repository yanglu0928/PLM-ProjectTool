# AUT-05-A13-P04 Windows11 隔离浏览器管理员改名

2026-09-28 / 0.1.0.dev0 / PASS（仅本机一次性合成账户与隔离环境）。

编码前检查：Phase2，Gate2/Phase1前置通过；冻结 `AUTH_USER_PATCH`、现有 Windows 显式写组合、A13-P01～P03 前端合同为输入。DEC-430 先登记风险/回滚/验收。只扩展测试夹具互斥的 `--user-name-browser` 模式；不改生产实体、Schema/Migration、API、权限或依赖。

首轮夹具启动失败：本机既有 PostgreSQL 18 服务已停止，尚未创建 `prj05a04_` 临时库；核状态与临时库数量为0，在原数据目录重新启动，WAL自动恢复完成。停止原因未证实，首轮不计通过。

恢复后，Windows11 隔离浏览器用合成部署管理员从列表进入目标用户详情，见初始 `ENABLED/"v0"`；在独立页面填写新名称、勾选目标/版本确认后提交。页面分别显示首次写入回执和独立 GET 当前详情，均为同用户 ID `01a0e69d-b4f4-7c3d-aaf7-9f58db67eeca`、新名称 `Synthetic Project Renamed Member`、`"v1"`。退出管理员后，原 `Synthetic Project Member` 登录显示“用户名或密码不正确”；新名称用同一合成测试密码登录成功，身份为普通用户且仍有原项目。

夹具 `VERIFY` exit0：SQL 核对同用户新 display/canonical、`ENABLED/lock_version=1`，改名审计 `USER_NAME_CHANGED` 恰一条；2个项目、2个测试Session、1个有效成员，自有服务、数据库/角色及 Vault 测试凭据清理通过。原 `--api-only` 模式另跑 exit0，匿名401、成员列表/详情200、跨项目404、管理员空列表/404及资源清理均通过。前端代码未变，P03的362测试/typecheck/build证据仍适用，本任务未重跑前端测试。

限制：本轮是 loopback HTTP 与合成 License/密钥，不代表正式 TLS/发行公钥/目标运行账户可信供给；未验证 Windows Server 2025、Debian 13、真实负载性能、POC-03质量、Gate3或可用安装包。兼容数据库 head0049，无升级步骤。回滚可撤测试夹具新模式，不涉及生产数据。
