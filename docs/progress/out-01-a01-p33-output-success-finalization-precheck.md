# OUT-01-A01-P33 编码前检查：Output成功终结Owner

- 日期：2026-11-05
- 结论：PASS_WITH_LIMITATION
- 变更记录：[CR-OUT-029](../changes/CR-OUT-029-output-success-finalization-owner.md)
- 前置：P32 PASS_SCOPE_LIMITED，详见[outcome](out-01-a01-p32-output-artifact-result.md)。

## 冻结与现状

冻结Output模型要求插件产生的协议合法暂存结果仍须经OutputService校验类型、大小、Hash并登记GENERATED_ARTIFACT DocumentVersion后，Artifact才可用；AVAILABLE需同时关联同项目OutputRequest、PluginExecution、FileObject、DocumentVersion与一致Hash。已完成的 P32 Migration 0232提供Artifact元数据Root与append-only校验结果表，以及数据库级AVAILABLE四项受控代码约束。Output现有P29/P30/P31 Start/Failure/Retry Owner均在同事务内协调Output与Jobs，按Output行先于Jobs claim的锁序；Jobs通用finish只负责当前租约下的通用Job终态，不核对Output业务成功证明。

## 单一问题与实现边界

本WBS仅补Output成功终结一致性Owner：在调用方已执行文件/插件相关工作之后，接收已经存在的Document/FileObject元数据和不可自由描述的验证facts；在一笔PostgreSQL事务中写Artifact/校验历史、Request成功、Job/Lease/Attempt成功与SYSTEM Audit。应用层只暴露内部端口，默认不装配、不挂HTTP。错Project/Request/Execution/File引用、旧lease、未完整校验及Audit失败必须整笔拒绝或回滚。相同有效执行的重放按冻结幂等策略收敛，不能重复Artifact。

明确排除插件子进程、Worker轮询、实际文件正文创建/原子提升和外部API。真实本地Storage发布需要后续单独WBS依ADR-008验证；P25的 initdb.exe 0xC0000135保留独立阻断。本验收不会使用伪造生产文件或客户资料。

## 依赖、风险与回退

- 依赖：P29/P30/P31当前Jobs与OutputOwner端口；PLG-03 Execution persistence；P32 Artifact Migration/ORM；Document FileObject/DocumentVersion关系模型；SYSTEM Audit接口。
- 主要风险：Job与Output Artifact状态分裂、项目交叉引用、已发布引用更新/多次发布、Audit失败但业务提交。
- 兼容性：代码层变化；冻结Schema、API和配置不变。数据库状态仅使用隔离合成PG18库。
- 回退：删除新增内部Owner和Repository/test，既有输出状态流无变化；无Migration、无数据迁移。
- 验收：GitHub hosted Windows D盘运行全量后端/wheel、前端/build、父包PG smoke及P33隔离PG18正负事务断言。P33不能凭P32结构验收替代。
