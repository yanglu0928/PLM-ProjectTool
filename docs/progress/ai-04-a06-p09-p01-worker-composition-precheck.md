# AI-04-A06-P09-P01 业务 AI Worker 组合前置核查

日期：2026-10-03；状态：`PRECHECK_PASS_WITH_REQUIRED_SPLIT`；依据 CR-AI-015～019、P06～P08、现有Windows服务组合。

核查确认P06～P08的安全组件本身已有证据，但生产`AI_PROVIDER_WORKER`仍只运行Provider Probe，业务`AI_TASK_EXECUTE`没有Owner专用领取、一步执行器或循环，因此当前不能称为可运行AI业务Worker。另有三项必须先关闭的组合缺口：通用claim会跨Owner领取；prepare失败发生在Invocation创建前而现有失败发布器要求Begun Invocation；业务Provider Execution Policy没有受信Bootstrap来源。

决定沿用一个厂商网络进程角色`AI_PROVIDER_WORKER`，在其内部保持Probe与业务Task两条独立策略/Adapter/Audit链，并用有界公平循环编排；不新造第五个SCM角色。实施拆为P02 Owner专用claim与pre-Begin失败，P03业务one-shot，P04公平循环/过期对账/排空停止，P05受信Execution Policy及Windows组合，P06 Windows11真实合成服务验收。详细偏差、迁移/回滚与验收见CR-AI-019和DEC-764。

Changed/Tests：本项只新增CR/决策/进度/状态/版本记录，未改程序、Schema、API、依赖或运行配置；静态交叉核对`service_windows`、Probe Worker/Loop、Jobs Lease、Grant/Prepare/Begin、send fence、success/failure publisher和reconciler。未运行新增代码测试，不标业务Worker PASS，也未访问Secret、Provider或客户数据。

Next：`AI-04-A06-P09-P02` 实现Owner专用AI Task claim与pre-Begin原子失败收敛。
