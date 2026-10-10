# P03-A04-P03 真实原子发布

## 编码前检查

当前Phase：Phase2。当前WBS：AUD-03-A06-A04-P03-A04-P03。
输入基线：CR-AUD-002/ADR010/CR-AUT-004/ADR011、0042。
前置任务：实际Worker渲染、Document存储/元数据、own结果Repository、Jobs caller-UOW完成、受控SystemActor来源限定验证通过。
涉及模块：Audit Owner编排，Document/Jobs/Platform仅公开Application Port。
涉及实体：已有Root/acceptance/capture/plan/File/result/Audit/Job/Lease；无Schema改变。
涉及API：内部publish(command, staged)，无HTTP或冻结API变化。
涉及权限：原User当前PM/Admin/License/Scope、原Job pair与Lease、受控SystemActor非授权；每阶段重核。
验收标准：真实受理到实际文件/元数据/结果/SYSTEM Audit/Job原子成功，双Scope空与多页，故障整UOW回滚、当前撤权/取消/过期拒绝，不持DB事务做Hash/提升。
风险：提升后DB失败文件保私有且STAGED，不冒充发布；整物理流程不盲重试，恢复/成功重放另验。正式运行账户信任材料与三平台仍待。

## 执行结果

限定内部真实发布PASS。先短UOW实际原User当前权限/原Root与受理/Job pair/Lease/完整capture/原plan预核，再事务外重读staging Hash；短UOW登记Document STAGED及原来源，结束后受控提升/完整Hash，最终同UOW Document AVAILABLE、实际SYSTEM发布Audit、own不可变Result、Jobs caller-UOW完成并迅速commit。系统身份每stage重新核来源；只DB阶段40P01限次整UOW恢复，物理流程不盲重试、不覆盖。

## 实际验收

`validation/aud-03-a06-a04-p03-a04-p03-publication/verify.py`在唯一临时PostgreSQL18数据库/临时中文目录执行真实Session/CSRF受理→claim→capture→render→publish，PROJECT/DEPLOYMENT、empty/260成员规范文件、完整Hash和manifest、AVAILABLE版本1/原元数据、SYSTEM源UUID+原actor/trace/purpose、不可变结果和Job SUCCEEDED实测通过。SystemActor使用当前Windows账户真实临时Vault，factory固定生产引用只映射测试引用；不读写正式材料，License仍是合成Guard。

提升后真实User撤权/真实Job取消/实际租约到期，以及合成License拒绝、真实临时系统材料丢失均不提交成功；File AVAILABLE写后、真实Audit追加后、真实Result写后、真实Job完成后的故障分别验证整最终UOW回滚，STAGED元数据/私有final保留，无结果/成功Audit/AVAILABLE事件，Job仍原状态。实际cancel-first/publish-first两线程数据库锁竞争由pg_stat_activity确认Lock等待；先取消则拒绝发布，先发布提交则取消返回原SUCCEEDED/changed=False，不回退成功。故障夹具与测试文件不作为业务数据。

5项新unit验证必要依赖/非法command无文件访问/身份缺失/错物理proof/阶段顺序与单次提升。全后端939项无失败（2既有Windows符号链接环境跳过），实际私有renderer/own结果Repository/Jobs completion回归通过。最终公开Port类型注解后重复真实发布验收通过；开发wheel0.1.0.dev0，567546bytes，SHA256 `6db434b5081964e527d7c201c4abe15d6cb1f5fe344aef4237b2c1898da08b8b`。无Migration/API/依赖，head0042不变，无生产升级。

## 遗留 / 下一任务

仅发布路径内部验收；正式运行账户材料/目标ACL/License信任源、Server2025/Debian、HTTP/下载、心跳调度/大文件性能/发行包仍未完成。提升后提交失败仅私有保留，不自动删除；同代重放不能从file形状制造成功，当前publish要求有效Lease且无已有结果。下一项`AUD-03-A06-A04-P03-A04-P04`真实来源受控恢复与当前权限成功结果重放，然后访问授权；CR-AUD-002整体仍IN_PROGRESS，Gate3未过。
