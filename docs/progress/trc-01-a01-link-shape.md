# TRC-01-A01：TraceLink 固定版本引用与边形状

- Changed：按冻结 DM-03/SC-02 限定 Trace 可用 `(owner_module, object_type)`、非空稳定 Object/Version UUID、GLOBAL/PROJECT 归属及七类关系；拒绝自环、跨项目、PROJECT→GLOBAL、非法 GLOBAL→PROJECT 方向，并从两端规范推导 Link Scope。任何引用均仅是形状，不是目标存在/正式状态/授权证明。
- Files：Trace 纯领域 `TraceVersionRef`/`TraceEdgeShape`、单元测试；Migration/API/新依赖：无；版本 `0.1.0.dev0`。
- Tests：Windows 11/Python 3.13 后端 587 项无失败（2 项既有符号链接环境跳过）；白名单、Scope、方向、自环、固定版本和恶意自报 Link Scope 测试 PASS；开发 wheel PASS，SHA-256 `fd46b825b8c05894f9996d0d44811bf8161cd3cee5a5efa4c2bb030e1bfd620f`。
- Result：A01 领域形状 PASS。缺目标 Owner Port、权限、正式状态、无环、持久幂等、Audit、逐节点图读取，TRC-01 整体和 Gate 3 未通过。
- Next：TRC-01-A02 持久结构/Migration 前置核查；Windows Server 2025 本项未运行，Debian 13 按用户指令暂不验证。
