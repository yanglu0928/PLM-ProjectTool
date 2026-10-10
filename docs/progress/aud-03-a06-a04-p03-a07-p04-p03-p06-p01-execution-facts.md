# P06-P01 执行器状态事实前置

日期：2026-09-27；状态：INTERNAL_READ_VALIDATED / EXECUTOR_WIRING_PENDING。

编码前：Phase2/P04-P03-P06-P01；CR-AUD-004/ADR011，前置当前代/历史收据、首取消来源、受控identity与静止锁均已验。涉及Jobs owned状态事实只读Port/Repository及Audit只读内部Owner；Job/Lease/Attempt，无Schema/API/依赖/权限扩张。

验收：实际原Root/acceptance/Job-Outbox及指定Worker/fence绑定，读取当前Job状态、实际原Attempt号/Lease状态/DB时钟alive与当前代关系，当前和历史代次明确分离。要求数据一致，不续租/改状态/commit/写Audit/读文件，不授权成功、失败、取消或重试，不接受客户端断言。受控SystemActor前后/同Supervisor静止，便于业务撤权后选择已有安全终止路径，仍不可读业务正文或绕过后续Owner/来源证明。

风险/回滚：状态可能随后改变，只是执行分支提示，实际转换/终态仍用已有Owner/来源核验；单一SUCCEEDED/FAILED/CANCELLED不是完成收据。仅内部未挂HTTP。验证两Scope真实RUNNING/RETRY_WAIT/新代后旧事实/SUCCEEDED/FAILED/取消及到期，错Root/Worker/fence与identity失败无写。撤未装配reader保历史；下一项P06-P02接单命令执行器，主循环/正式包/Gate未完成。

Changed/Files：Jobs ExecutionFacts DTO/owned Port与LeaseRepository只读实现，Audit受控内部Reader，unit/独立实际验证脚本及决策/状态/版本/CR记录。Migration/API/依赖无变化，0042保留，无生产升级。error_code仅固定安全格式且repr隐藏，事实不含文件路径/正文/Key；DTO拒历史ACTIVE、当前ACTIVE终态等非法组合。

Tests/Result：5新unit，Windows11/Python3.13后端完整1047项无失败，2既有Windows权限环境跳过。实际PG18临时库/Windows临时Vault两Scope，真实RUNNING→RETRY_WAIT→5秒后新claim、旧代hint不current而新代actual attempt2 current→FAILED，以及真实发布SUCCEEDED、实际2秒到期仍ACTIVE但alive=False、技术取消CANCEL_REQUESTED→CANCELLED/EXPIRED，每读六表snapshot无写。原User停用+License撤销仅内部hint可读，实际capture拒绝；错Root/Worker/fence/第二identity丢失拒绝；原发布fixture通过。技术取消样本特意缺SYSTEM完成源，证明状态hint非完成receipt，不冒充取消Owner新增验收。

初次unit3项错误为新fixture漏传必填error_code，修正测试参数None并新增非法组合测试，未修改参数默认或放宽校验；完整unit/实际PG重跑通过。开发wheel611308字节，SHA256 91cf441f6d918745b2da1875de481bc92d920f7dd1d74094cb338b8fb100f5d4，构建通过，不是可用安装包。

Known Issues/Next：P06-P02把已验证成功/失败/取消/重试及原源确认接线；Reader短静止锁不是跨进程锁或OS强杀，主同步I/O须先返回，状态hint不保证转换时仍相同。没有新增并发竞争/网络断线/目标账户/Server2025/Debian发行验收；整体包/Gate与完整Scope持续待完成。
