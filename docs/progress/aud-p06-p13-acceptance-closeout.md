# P06-P13-P08：有界调度隔离验收收口

日期2026-09-27；Phase2/Gate2基线64cdf09保留；前任务acca660。输入CR-AUD-005/P01～P07实际代码和验证；本任务仅核对证据、更新风险/操作说明，不修改产品或Gate。

## 覆盖矩阵

|要求|权威证据（validation内verify.py）|结论与边界|
|---|---|---|
|锁队首绕行/释放后执行/双候选互斥|aud-p06-p13-queue-isolation|双Scope实际PG通过；只锁不写候选非授权|
|坏引用/缺Root/错pair后健康执行|同上|六表无写拒绝、坏Job无Attempt、恢复合成来源发布通过|
|第三次耗尽坏来源不挡正常准入|aud-p06-p13-exhaustion-isolation|双Scope各三场景通过，坏Job/Lease/Attempt不动；恢复源后原安全收尾/lost-ack/旧字节通过|
|混排持续循环/正常停止|aud-p06-p13-mixed-loop|两组固定队列各12健康完成、坏行不动、STOPPED；25步/12拒绝，不是吞吐保证|
|新队首可见/末尾回绕/常数状态|aud-p06-p13-scan-window及queue-isolation、1132 unit|双Scope新head在31原完成后执行；每实例cursor+计数，无无限排除集；32不是秒数|
|反向锁序/有界死锁重试/锁超时|aud-p06-p13-real-deadlock|8实际40P01、2实际55P03通过；错误不当坏source，不改生产超时|
|已知命令提交确认不盲重领|aud-03-a06-a04-p03-a07-p04-p03-p06-p06-claim-confirmation|提交前回滚与提交后lost-ack原源重验通过；非真实网络中断/跨进程未知命令恢复|
|真实Windows子进程停止|aud-p06-p12-pg-child|实际PG/Credential/Vault身份、明确合成License；idle无写/active单次排空通过；非SCM/无限阻塞/正式License|
|原接受审计不可变|mixed-loop|实际UPDATE被P0001拒绝、六表无写；不是实际源损坏恢复通过|

本矩阵证据来自前轮实际执行结果及当前源码，未再次运行相同完整测试，不把代码审阅称运行PASS。后台源隔离有限子任务内部验收完成；CR整体、Gate3、三平台发行、完整产品交付均不关闭。

## 必须保留的风险

1. Acceptance源损坏分类仅单元覆盖，合法运行库不可变保护已验证；不关闭触发器制造伪成功，也不自动修复权威来源。
2. 耗尽预检与最终expire之间的竞争、复杂Lease不一致、真实断线/未知跨进程命令恢复尚未完整验证；Owner最终证明和未知错误失败关闭不可移除。
3. 20Worker/无限持续流公平/吞吐P95、服务SCM/硬终止、正式公钥和运行账户来源、Server2025未验证，Debian13按用户指令暂缓。
4. SOURCE_REJECTED仅技术诊断；不变更Job终态，不代表“队列为空”。IDLE可能当前窗口末尾，下一轮才回绕。

## 下一实现链

公开任务详情→可选HTTP→Windows显式装配→审计导出POST受理，随后按独立任务完成列表/cursor、取消If-Match和受控重试。不能用只支持Audit的替代端点冒充冻结通用Jobs；具体前置见 `job-01-a01-read-preconditions.md`。此排序不取消原公开API、其他任务Owner、完整业务主链或最终安装包要求。

Changed：验收矩阵/CR状态/运行说明；Migration/API/代码：无；Tests：本轮未新增运行、引用可追溯前轮证据；Result：文档收口PASS，整体IN_PROGRESS；回滚撤本轮文档增量，历史不改。
