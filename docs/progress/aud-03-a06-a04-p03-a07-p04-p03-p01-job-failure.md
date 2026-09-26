# P04-P03-P01 Jobs事务内失败Port

日期：2026-09-26；状态：TECHNICAL_PORT_PASS / OWNER_PENDING。

编码前检查：Phase2/P03-A07-P04-P03-P01；单一问题为Jobs owned caller-UOW原审计Job失败技术转换。前置原pair/current check/retry_or_fail与单次协调PASS，输入CR-AUD-004（Owner政策未实施）、既有Jobs三次尝试限制。涉及Jobs Application/既有Job/Lease/Attempt，无Schema/API/权限/依赖改变。

实现边界：原request/Ref完整pair→当前Worker/fence/alive Lease/Attempt及claim→既有owned retry_or_fail；只在caller UOW操作，不commit、不读跨Owner表/Root、不做I/O。固定白名单error_code，retryable必须bool、delay有限int，max_attempts原3保持；调用者选择策略并负责真实Root/受控身份与同UOW审计。本Port不验证业务权限，不将技术状态当成果或授权。

验收：严格坐标/政策输入、原pair/mismatch、实际双Scope失败/限次retry/真实新代/旧代拒绝、结束Attempt/Lease绑定，caller后置真实Audit失败整UOW回滚、成功/取消/过期拒改。Owner安全终止授权与Audit证明留P02，不能跨模块顺手开放主循环或POST。

实测：5新unit通过；隔离PostgreSQL双Scope FAILED/三次限额RETRY_WAIT、实际新代/接管拒旧代、Attempt错误/完成时间与Lease RELEASED绑定；不commit及真实Audit插入后caller异常整UOW回滚；成功/取消/实际过期/错Worker/fence拒改六表快照不变，私有stage字节保留。复用原发布全回归通过。脚本首次误用plan.coordinate失败，修正为实际staged.content.coordinate后从新临时库完整重跑通过，不掩盖失败。

Windows11/Python3.13完整998项无失败（2既有符号链接权限跳过）。开发wheel 586587 bytes，SHA256 `75e6b5c1b2bd0c18e8c2246ff2dd19fcb7becf234f8d0441b1ec2fb5829f57b5`；首次相对PYTHONPATH导致build子进程找不到setuptools，改绝对依赖路径后成功。不是安装包。无Migration/API/依赖，0042不变，无生产升级；回滚撤未装配Port、保留历史。Owner策略/权限、取消、主循环及正式发行未通过。
