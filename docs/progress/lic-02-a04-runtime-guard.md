# LIC-02-A04：运行时许可检查与失败关闭

- 日期：2026-09-24；结果：PASS（仅内部 Guard）；依据：Gate 2、ADR-006、DM-02、CR-LIC-001、DEC-20260924-093。
- Changed：受许可操作需从活动安装读取不可变文档并核对验证事件/状态，不使用旧 VALID 作为单独放行依据。状态行锁贯穿受信任时间版本读取、Ed25519/机器/有效期/时间综合重验及事件/状态/Audit 写入；过期、机器不符、时间回拨、状态损坏或写入失败均拒绝。状态拒绝后由后续受控恢复命令处理，不由普通 Guard 自动复活。
- Files：`runtime_guard.py`、`runtime_guard_repository.py`、`trusted_time.py` 小范围只读版本端口、单元测试与 PostgreSQL 临时库验证脚本。Migration：无。API：无公开路由。Permission：Guard 不代替 Session/Role/资源授权。
- Tests：Windows 11/Python 3.13 后端 174/174 PASS；Guard 单元覆盖率 92%；PostgreSQL 18.6 临时库真实合成 Ed25519/机器/有效期链、两请求串行、未安装/过期拒绝与审计回滚 PASS；LIC-03-A02 可信时间集成回归及 wheel 构建 PASS。Windows Server 2025、Debian 13 本任务未运行。
- Known Issues：测试使用进程内合成公钥与可信时间替身，不能作为生产信任源验收。运行时每次检查写数据库事件和 Audit，性能目标未验收；可信时间推进与结果记录分属事务，后者失败时本次 Guard 仍拒绝。受控恢复、HTTP Guard 挂载及生产公钥/选定 MAC/可信时间密钥来源与初始化尚未完成，不可开放业务或通过 Gate 3/UAT。
- Next：LIC-02-A05 受控重验证与状态恢复。
