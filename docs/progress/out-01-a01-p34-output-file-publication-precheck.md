# OUT-01-A01-P34 编码前检查：本地Storage与OutputArtifact一致性

- 日期：2026-11-05
- 结论：PASS_WITH_LIMITATION（可进入Storage-only发布协调实现；不得在本WBS打开生产装配）
- Change Request：[CR-OUT-030](../changes/CR-OUT-030-output-artifact-file-publication.md)
- 前置：P32 PASS_SCOPE_LIMITED（Migration 0232/Artifact持久化），P33 PASS_SCOPE_LIMITED（成功终结Owner及严格重放）
- 执行位置：基于GitHub分支源码只读检查；未在用户本机/C盘运行程序

## 编码前检查合同

**当前Phase：** Phase 2 Platform Core。  
**当前WBS：** OUT-01-A01-P34。  
**输入基线：** ADR-008本地文件系统与PostgreSQL元数据；冻结DM-03/OUT-02；CR-OUT-028/029；Migration 0232；P33验收结果。  
**前置任务：** P32与P33均PASS_SCOPE_LIMITED；Document FileObject Storage及发布恢复原语已存在。  
**涉及模块：** document.infrastructure（LocalFileStorage）；document.application（FilePublishService/恢复端口）；output.application/infrastructure（新增内部协调Owner，仅当不需Schema/API变更）；jobs/Audit作为P33后置收敛。  
**涉及实体：** STAGED FileObject及locator、GENERATED_ARTIFACT Document/DocumentVersion、OutputRequest、PluginExecution、OutputArtifact、Job/Lease/Attempt、Audit。  
**涉及API：** 无公开API变化，不新增HTTP/Worker/default composition。  
**涉及权限：** 内部Output生成Job的Project与fencing Claim；SYSTEM审计且保留原请求用户归属；Storage root/locator授权仅由Document适配器执行。  
**验收标准：** 使用纯合成内容在GitHub hosted Windows Server 2025 D:临时目录与隔离PG18中，验证暂存文件身份/Hash/大小、同卷无覆盖提升、提升后Hash、DB事实二次校验、fencing失效拒绝、相同成功重放不变；失败或进程中断必须能精确分类stage-only/final-only/linked-pair/unknown；Audit/DB故障不盲删文件、不伪造AVAILABLE；全量后端/wheel、前端/build和既有父包验证保持通过。  
**风险：** 文件系统和PG18不能构成单一ACID；硬链接提升存在linked-pair窗口；用户态事务失败可能留下final-only；并发重试/未知文件绝不可自动清除。  
**范围：** 仅内部发布协调协议/隔离验证。无客户数据、产品API、默认平台装配、插件执行、正式发行、C盘或用户本机程序执行。

## 核查结果与实现边界

1. LocalFileStorage.publish_verified 已在事务外执行流式大小/Hash验证、普通单链接文件及重解析点校验、同卷无覆盖硬链接提升、删除暂存名后再次验证最终内容；verify_content会复核文件描述符与路径身份及mtime/size/link count。
2. inspect_recovery可以只读分类NONE、STAGE_ONLY、FINAL_VERIFIED、LINKED_PAIR、BOTH_UNRELATED和UNSAFE；现有有限恢复方法要求数据库调用方先证明目标记录仍可恢复。该能力可作为状态机，不可扩大成目录扫描后自动删文件。
3. Document FilePublishService遵循“短DB事务授权和快照→DB锁外发布→短事务重授权并更新FileObject/Audit/幂等收据”。这为文件/数据库非原子窗口提供已验证的设计先例；它不是Output授权的替代品，也不能由Output直接绕过Document状态Owner。
4. P33要求传入文件对应的FileObject、GENERATED_ARTIFACT Document与DocumentVersion已经是同Project/同Hash/MIME/Size且AVAILABLE，再与Artifact/Job/Audit同事务提交。因此P34不能简单把P33的数据库事务改成长事务包住文件I/O，也不能直接复用P33去接受STAGED元数据。
5. 预期新增逻辑必须协调Document现有发布状态Owner和P33完成Owner，且每个DB边界之前/之后复核同一Project、request、execution、FileObject/Version、Hash/Size/MIME及当前fencing token。成功数据库状态以P33为最终权威；若文件已提升而后置事务失败，保留final-only及其数据库证据供受限恢复，不能自动删除或倒写。

## 决定与后续步骤

按CR-OUT-030方案B进入实现，但把P34第一步严格限为“内部、可调用、未装配的输出文件发布协调Owner + Storage-only/PG18集成验证”。开始实现前先补齐当前Document版本创建/发布次序和恢复审计适配器源码核查，并在CR中登记任何必要偏差。若现有接口不能安全表达/重放最终DocumentVersion事实，则停止接线，先以独立WBS补齐该接口；不得用临时SQL、绕过FilePublishService、伪造AVAILABLE或引入schema扩张。

## 退出条件

P34只有在托管 Windows hosted D:运行文件系统边界测试、PG18事务前后状态/恢复测试及全量回归通过后才能PASS_SCOPE_LIMITED。任何RUN只通过部分断言时必须如实拆分、修复后重跑。P25 0xC0000135、Windows 11设备验证、Gate 3及Pilot仍为独立未通过项。
