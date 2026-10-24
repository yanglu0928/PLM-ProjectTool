# AI-01-A05-P05-A03-P04-P02-A03-P01：探针 Worker 维护准入循环

日期：2026-10-02；状态：内部限定范围 PASS。依据 ADR-007/012、CR-AI-002、DEC-20261002-660。

## 本项范围

`ProviderProbeWorkerLoop` 以固定 WorkerRef 串行执行现有单次 Worker；每轮先取得 PostgreSQL 维护共享锁并确认 RUNNING，锁跨领取、Secret 使用、网络 I/O、结果/Audit 发布。停止信号仅阻止下一轮，不强行中断正在进行的探针；`quiescent` 忙时拒绝，只有当前轮完全退出后可释放资源。

不注册 Windows 服务、不运行真实外发，不开放 Test/Activate 路由。生产 DNS 解析尚非有界，下一项 P02 处理其与 60 秒租约窗口；P03 才处理新增 SCM 固定角色、进程标记与运维清单，P04 再审 Test 路由挂载。

## 验证与回滚

- Win11 单元4项：每轮持准入、进入锁前 STOP、工作中 STOP 等待排空/静止拒绝、维护拒绝及异常释放。
- `validation/ai-01-a05-p05-a03-p04-p02-a03-p01-worker-loop/verify.py`：全新临时 PG18 簇，真实会话共享锁阻止排他维护转换；轮后锁释放，MAINTENANCE 状态阻止再次执行。该脚本使用合成 Worker，不发送网络请求。旧临时测试簇因 `pg_notify` 缺失无法启动，未修补或覆盖；新簇测试后已安全停止。
- 后端2018项运行/3跳过、开发 wheel SHA-256 `61989c77d1a1728312fbc52bd7fc6bd0d8970b2f2561170012058`。无 Migration/API/依赖；撤未装配循环即可回退，历史 Job/Audit 保留。
