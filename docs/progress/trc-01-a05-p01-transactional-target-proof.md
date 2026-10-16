# TRC-01-A05-P01：同事务 DocumentVersion 目标证明

- Changed：按 `CR-TRC-001` 将内部 Trace Owner Port 改为接受调用方事务；Document 受控证明在该事务内执行真实 Session/License/Scope/Project 授权，锁定 Project/Member/Department 及 Document/Version/FileObject 行，固定版本不可用或撤权后失败关闭。已有 Document 只读 API 不变。
- Files：Trace 目标证明、Document 组合适配与只读服务/Repository、单元测试、隔离数据库验证脚本、CR、状态与版本说明。Migration/公开 API/新依赖：无；版本 `0.1.0.dev0`。
- Tests：Windows 11/Python 3.13 后端 595 项无失败（2 项既有符号链接环境跳过）；隔离 PostgreSQL 18.6 真实 Session/Scope/GLOBAL/PROJECT 授权、同事务 FileObject/Member 更新锁超时、撤权后拒绝 PASS；开发 wheel PASS，SHA-256 `493ac4a9196f8a054e39e76fcaa82913576af84bf920d9632d370354699f6fed`。
- Result：事务内目标证明 PASS。现有代码仍只有内部证明与无环 Guard，未实现 Trace 创建命令/持久幂等/Audit；其他 Owner 未注册。Gate 3、生产信任源、可用程序包及 Windows Server 2025 均不得标 PASS；Debian 13 按用户指令暂不验证。
- Next：TRC-01-A05-P02 内部创建命令，保证证明、无环、持久幂等和 Audit 在同一事务。
