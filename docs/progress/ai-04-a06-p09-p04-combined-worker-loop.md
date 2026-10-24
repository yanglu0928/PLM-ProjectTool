# AI-04-A06-P09-P04 公平组合 Worker 循环

日期：2026-10-03；状态：`COMBINED_WORKER_LOOP_PASS`；依据 CR-AI-019、DEC-764～767，无公开 API、Schema 或第三方依赖变化。

新增单线程组合循环：每个获维护准入的周期先执行最多 1 项（可配置上限 1～64）的过期业务 Task 对账，再以业务 Task 和 Provider Probe 为两个独立执行族公平调度。两个执行族都繁忙时按终态结果严格交替；首选族空闲时同轮回退另一族，但下一轮仍先检查刚才空闲的族，避免持续繁忙一侧饿死新到任务。每轮最多产生一个非空闲执行结果，对账积压不能无限占用周期。

停止采用 sticky 协作信号：已进入的有界网络调用正常排空，停止后不启动回退链或下一周期；`quiescent` 仅在循环锁和维护准入均已释放后成功。维护共享锁覆盖对账、claim、Secret、网络和结果发布；空闲等待发生在锁外。

验证：新增 7 项单元覆盖公平、空闲回退、对账顺序/上限、维护拒绝、无效结果、网络排空和静止边界；相关 Worker/对账 27 项通过。Windows 11/PostgreSQL 18.6 一次性数据库以真实 `PostgresMaintenanceAdmission` 证明工作期间独占维护锁不可取得、四轮业务/Probe 为 2/2、静止后可立即独占，并回归 P03 真实业务 one-shot 整链。后端全量 2301 项通过、3 项既有条件跳过；最终 wheel 805 项且包含组合循环，SHA-256 `3f7a696b5a7218b865fdad75054865acfe4e09db55e6d2fb9df6788b2d8a82ec`。系统 Python 3.13 因本机缺 `setuptools.build_meta` 首次未产物，改用项目已验证的 Python 3.13.15 构建环境后成功；未修改生产依赖。零真实 Provider 网络、真实 Secret 或客户数据外发。

兼容/回滚：新循环尚未接入生产入口，既有 Probe-only 循环保持；可撤新增内部模块恢复旧行为，已持久化 Task/Invocation/Job/Audit 不变。对账继续严格限于 P08 已验证的、具有 current Invocation 的过期业务 Task，不在本项静默扩大数据库终态语义。

Next：`AI-04-A06-P09-P05` 严格非 Secret Execution Policy Bootstrap 与 Windows `AI_PROVIDER_WORKER` 生产组合。
