# P03-A07-P02 Audit 当前授权心跳

日期：2026-09-26；状态：PASS（内部短事务受权心跳；调度/实际长任务待）。

编码前检查：Phase2 / P03-A07-P02；输入原当前权限/Capture绑定锁序、P01 Jobs caller-UOW renewal PASS。新增Audit内部心跳Application类，继承既有capture能力/完整原源检查；无Schema/API/角色/技术栈变更。renewal独立显式注入，不使用自提交通用Service。

每次新短UOW：无锁peek原根仅定位→实际当前enabled原提交User/PM成员部门或部署Admin/License→锁根与原acceptance/pair→当前Job/Lease/Attempt→caller-UOW续租→再次当前授权与期限检查→commit。原CAPTURE/RENDER/PUBLISH阶段均按相同当前权限，stage限定原三值，不虚构新权限。logout不是async取消；User停用或真实角色/成员撤权不能保活。心跳不读写文件、不改capture/计划/成果/业务Audit。

验收：严格命令/阶段/时长；真实双Scope原源与权限续期、原User/PM/部署角色撤权、License拒绝、取消/过期/接管与跨Root绑定拒绝、续租写后故障/结束前撤权回滚、短事务锁序/原发布回归。周期线程/停机/长任务协调留P03，不冒充已有后台运行能力。

## 实施结果

- Changed/Files：新增Audit `worker_heartbeat.py`，复用既有Capture原源/权限/租约锁序，显式注入Jobs owned renewal；5unit、真实隔离PG验证脚本及配套状态/决策/版本说明。依然保留原CAPTURE/RENDER/PUBLISH三stage，没有新增角色或权限。
- Migration/API/依赖：无，head0042；不挂HTTP、不做文件I/O、不生成业务Audit/成果，不使用Session为异步保活。撤未装配新服务保历史可回滚，无数据升级。
- Tests：5新unit实际执行，完整原源与双授权/租约检查、strict坐标/阶段/时长、前置拒绝不renew、结束前授权或Lease失败不commit、改变claim/底层异常安全化通过。
- 实际PG18：双Scope每个原stage授权续期成功；13表完整快照证明仅Job/Lease期限/heartbeat改变，Root/acceptance/pair/capture/attempt/plan/File/Result/Audit历史不写。真实User停用、PM→实施成员、部署Admin→NONE、License、错Worker、不同Root/Job误绑、成功终态、取消申请、实际2秒到期拒绝无写；实际接管旧代拒绝、新代原受理源续租通过。真实renew写后注入故障及renew后License拒绝都整事务回滚期限。
- 原发布完整回归通过，Windows11/Python3.13全后端973项无失败（2既有符号链接权限跳过）。开发wheel成功579253字节，SHA256 `bacf6e87d2d635854769b47083cbbd29949fe79e9b2c7eb692ab176ff9d78a53`，非安装包。
- Result：内部受权短事务心跳PASS，不等于周期线程/长任务或后台运行入口通过。继承原最多3次真实死锁分类整UOW重试；本轮没有新增独立真实死锁注入证明，不扩大该项声明。
- Known Issues/Next：P03有界周期心跳协调器（停止/失败传播/长文件I/O无DB锁/发布收尾竞争），随后Worker循环/失败取消恢复与提交Jobs HTTP。License合成、发布身份临时Vault，正式账户/三平台/质量/性能/Gate3/UAT/完整可用包仍待，POST关闭。
