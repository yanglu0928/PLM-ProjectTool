# CR-OUT-031：Generated Artifact DocumentVersion 的受控创建前置

- 日期：2026-11-05
- 状态：已登记；按P34编码前源码审计拆分执行
- 来源：OUT-01-A01-P34；承接CR-OUT-030
- 适用基线：ADR-008、冻结DM-03/OUT-02、Migration 0220～0232、Document FileObject/DocumentVersion Owner、P33成功终结Owner
- 执行限制：只允许GitHub hosted/云端沙箱；不得在用户本机或C盘运行项目代码

## 发现

源码审计确认现有DocumentVersionCommitService仅用于上传文档，并明确拒绝GENERATED_ARTIFACT；它要求FileObject已是AVAILABLE且位于最终locator，随后在同一数据库事务创建AVAILABLE DocumentVersion、添加UPLOAD source ref并推进Document.latest_version。P34所需的系统生成版本没有对应Owner和非UPLOAD来源类型。P33成功终结Owner则要求匹配的Document、DocumentVersion、FileObject均已存在且AVAILABLE。因此仅围绕Storage做协调或直接复用上传Owner都不能构成安全的Output发布流程。

## 执行调整

将CR-OUT-030的P34实施拆为两个单一问题：

1. OUT-01-A01-P34A：在无Schema/API/default composition变更下，实现仅供内部调用的Generated Artifact DocumentVersion提交Owner。要求绑定PROJECT、GENERATED_ARTIFACT Document、具体OutputRequest/Execution/Job fencing、AVAILABLE最终FileObject与hash/size/MIME；同事务创建不可变版本、来源引用、Document latest-version、SYSTEM Audit及幂等/并发保护。未知来源、错绑定、历史重放不一致均失败关闭。
2. OUT-01-A01-P34B：在P34A托管验收后，实现STAGED到最终FileObject的Storage发布协调，使用既有同卷无覆盖提升和恢复分类，再调用P34A与P33完成Owner；外部文件系统与PostgreSQL不宣称跨资源ACID，final-only/linked-pair/unknown保留受限恢复状态，绝不盲删。

## 基线差异、风险与回滚

- 差异限于新增内部DocumentVersion Owner与两段式发布编排；不修改冻结表结构、API、locator、默认组合、Worker或插件执行。
- 主风险为Storage提升后DB失败的final-only窗口及fencing过期竞态。以身份/Hash复核、精确数据库绑定、幂等事务和失败保留/恢复分类控制。
- 若审计发现冻结Schema无法表达来源或绑定，则停止写入并另提CR；不得以SQL绕过现有Owner或伪造AVAILABLE。
- 回滚：新增Owner保持未装配；按DB事实与文件身份分类，不删除已提升文件。代码可撤回，历史版本/审计证据保留。

## 验证计划

GitHub hosted Windows Server 2025 D盘临时目录 + 隔离PostgreSQL 18、纯合成数据。先做P34A单元与PG事务验收（首次提交、精确重放、错Project/Request/Execution/Document/File/Hash、旧fencing、并发、Audit失败全回滚、历史不可变和Migration保持不变），再做P34B真实Storage边界（同卷、hash/size、无覆盖、final-only/linked-pair/unknown恢复分类及故障注入）。全量后端/wheel、前端/build、既有父包验证仍须通过。P25 0xC0000135独立阻塞不视作P34失败或通过；Win11/Pilot/Gate/Release状态不变。