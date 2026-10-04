# HND-01-A03-P01：HandoverAnalysis identity 创建 Owner

日期：2026-10-05。结论：`HND_01_A03_P01_ANALYSIS_CREATE_PASS`。下一项：`HND-01-A03-P02` 完整 Draft AnalysisVersion 创建 Owner。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：HND-01-A03-P01
输入基线：DM-05、API-04、Schema0096、CR-HND-001、DEC-847/848
前置任务：HND-01/HND-02八表Schema/ORM及Owner关闭已通过
涉及模块：handover application/domain/infrastructure；project/document/auth/license/audit/idempotency Port
涉及实体：HND-01 HandoverAnalysis identity；本项不创建HND-02 Version
涉及API：冻结HND_ANALYSIS_CREATE语义；本项不挂HTTP
涉及权限：ProjectManager、ImplementationMember；当前Session/CSRF/ACTIVE Project Member
验收标准：固定PROJECT DocumentVersion来源、服务端摘要、幂等并发、Audit同事务、撤权重验
风险：跨项目或损坏文件被纳入来源；重放绕过当前授权；identity创建被误称为分析结论
```

## 实施结果

- 新增 Handover 专属 `handover-source-set.v1` 规范摘要及 PROJECT DocumentVersion 验证器，只接受同项目 ACTIVE Document、AVAILABLE Version 且底层文件元数据一致的固定来源。
- 新增 Analysis identity 创建服务与 SQLAlchemy Repository；ProjectManager/ImplementationMember 当前写权限、Session/CSRF、License、持久幂等、Audit 与写入在受控边界完成。
- 创建结果固定为 ACTIVE、零正式版本、`ETag "v0"`；只写 HND-01 identity，不生成 Version、Item、AI建议或客户事实。
- 中央 Project 权限表新增冻结 `HND_ANALYSIS_CREATE` 角色规则。重放仍重验当前 Session/项目成员资格；同 key 不同 payload 返回幂等冲突。

## 验证与证据

- Windows 11/PostgreSQL 18.6 临时库真实验证：PM/Implementation成功、CustomerManager/错误CSRF/失效License/跨项目来源拒绝、同key重放、冲突、两线程并发、Audit失败整笔回滚、零Version边界及成员暂停后重放拒绝均通过；临时库已删除。
- 首轮夹具因 FileObject 与 DocumentVersion 摘要不同被 Document Owner 正确拒绝；修正合成夹具一致性后从新库完整重跑通过，未放宽产品校验。
- 定向16项、后端全量2606项通过，3项按既定环境条件跳过；`compileall`、`git diff --check`通过。
- 最终开发wheel解包定向16项通过，SHA-256 `2021d3ddf09a03ddd1b5f67a6c78df1057b8fe226c46c5a7b6f3a6aac852f586`。

## 兼容、回滚与未关闭项

复用Schema0096，无Migration、公开Router、生产配置、依赖、网络或客户数据外发变化。停止装配创建服务即可关闭新写入；合法 identity、Audit 和幂等收据保留，不删除历史。

完整 Draft Version/Item、Validate、Review、Action、HTTP/UI/Workflow、真实资料质量、正式信任、性能及目标平台发行仍待；identity创建成功不代表分析已生成、已确认或Gate 3通过。
