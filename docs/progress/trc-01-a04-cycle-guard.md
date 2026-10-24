# TRC-01-A04：受控关系写入期无环 Guard

- Changed：Trace 基础设施新增仅在活动事务中执行的受控关系 Guard。`DERIVED_FROM`/`SUPERSEDES` 使用同 Scope/Project 事务级 advisory lock 和去重递归可达性检查；新边的 target 若能到达 source 即拒绝。其他关系不作无环断言。Guard 必须与未来创建命令的目标证明、插入和 Audit 在同一事务，不能作为独立安全边界。
- Files：Trace 基础设施 Guard、单元测试、`validation/trc-01-a04-cycle-guard/verify.py`；Migration/公开 API/新依赖：无；版本 `0.1.0.dev0`。
- Tests：Windows 11/Python 3.13 后端 595 项无失败（2 项既有符号链接环境跳过）；隔离 PostgreSQL 18.6 直接/混合关系环、项目隔离、两条并发事务等待提交后拒环 PASS；开发 wheel PASS，SHA-256 `f4ac362eef35bf075ff5495746a6f6736ba2d900809ed72c5633e21c40061969`。
- Result：Guard 本身 PASS。尚无正式 Trace 创建入口，直接数据库写入不受该应用 Guard 保护；不能标 TRC-01 整体、Gate 3 或可用程序包通过。
- Next：TRC-01-A05 创建命令前置核查及同事务目标证明/无环/幂等/Audit；Windows Server 2025 未运行，Debian 13 按用户指令暂不验证。
