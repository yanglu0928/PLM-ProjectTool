# AUT-03-A02：登录限流策略与持久化边界

- 日期：2026-09-25；结果：PASS（仅内部限流服务）；依据：冻结 API-02、CR-AUT-001、DEC-20260925-007。
- Changed：新增 Auth 私有短期窗口桶 ORM/Alembic `20260925_0012`；来源 30 次/5 分钟、账户 10 次/5 分钟双维度限制。每次尝试在独立事务预约并提交，使用 PostgreSQL 数据库时间与原子 UPSERT；数据库不可用则拒绝。只保存 SHA-256 摘要键、窗口与计数，不存原始 IP、用户名、密码或 Token。异常及超限不回显主体信息。
- Files：`login_rate_orm.py`、`login_rate_repository.py`、`login_rate_limit.py`、迁移/元数据注册、单元测试、`validation/aut-03-a02-login-rate/verify.py`、决策/变更/状态/版本说明。Migration：`20260925_0012`，上线前备份并执行 `upgrade head`；有桶数据时普通 downgrade 拒绝，维护窗口清理后可回退到 `20260924_0011`。API：未挂公开登录路由。Permission：匿名登录前的统一限流 Port。
- Tests：Windows 11/Python 3.13 后端 215/215 PASS；目标限流服务覆盖率 96%；PostgreSQL 18.6 空库 up/down/re-up、已有用户升级、ORM drift=0、约束、账户/来源限额、40 并发、窗口重置、非空回退拒绝与维护后回退 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本任务未运行。
- Known Issues：摘要不等于匿名化，数据库需要最小权限；来自代理的真实客户端地址仍须可信代理策略，不能直接读取任意 `X-Forwarded-For`。短期桶保留清理调度、误拒/压力评估和 HTTP 登录接线尚未完成；当前登录仍 404。
- Next：`AUT-03-A03 登录用户名/密码证明与 Session 签发编排`。
