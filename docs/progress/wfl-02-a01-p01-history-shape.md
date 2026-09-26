# WFL-02-A01-P01：成功相邻迁移历史形状

日期 2026-09-26；程序版本 0.1.0.dev0；结果 DOMAIN_SHAPE_PASS，不是 Gate/迁移服务/数据库 PASS。

## 编码前检查

- Phase：2 Platform Core；WBS：WFL-02-A01-P01，单一问题为追加成功迁移快照的纯领域结构。
- 输入：冻结 DM-02 StageTransition、SC-01 WFL-02、API-02 Workflow；CR-WFL-001 配置 V1 与 CR-WFL-002 状态语义。
- 前置：固定六阶段/十二项配置、相邻结构校验、Workflow 实例结构和查询已完成；本任务不要求未完成的 Owner/Gate 查询，因为没有写服务。
- 模块/实体：仅 workflow.domain；ForwardTransitionSnapshot、GateItemSnapshot，不访问其他模块的内部实体或表。
- API/权限：无 HTTP/CLI/应用服务入口，无权限放行；未来写入口仍须 PM/Session/CSRF/License/项目非归档及乐观锁/幂等。
- 验收：只接受五组相邻阶段、固定来源阶段的完整有序清单；不可变；UUID/UTC/理由/锁版本校验；快照仅 PASS/WAIVED，完整豁免依据；拒绝缺项/跨阶段/伪造嵌套初态。
- 风险：结构合法不证明引用存在、归属、访问权、批准或制品完整；未来服务必须通过公开 Port 做同事务事实证明，不能接受客户端创建的对象作为 Gate 证明。

## 实施

`workflow/domain/history.py` 新增两个 frozen/slots 值对象：

- GateItemSnapshot：固定 item key、PASS 或 WAIVED、非空且无重复的 Evidence/ReviewRound UUID 引用；WAIVED 独立保留 actor、reason、impact 和批准例外引用，不能把它改写为 PASS。无客户正文。
- ForwardTransitionSnapshot：Workflow/Project/actor/trace 身份、定义版本 1、from/to、before/after 锁版本（+1）、原因与 UTC 时间，以及来源阶段全部必需项的固定顺序快照。嵌套对象重新校验，禁止空快照、重复/遗漏/跨阶段/动态 key。

上述 UUID 是历史引用形状，不是签名或可信证明。Evidence 引用须由 Evidence Owner 对固定不可变记录解析；ReviewRound/例外的真实范围和批准状态留给 Review/例外 Owner。当前不创造这些记录、不访问数据库、不自动产生客户确认。不能凭空把 UUID 当有效依据。

本值对象只支持相邻前进；START、BLOCKED 恢复、最终完成与纠正类型未在本任务定义，不借用虚构第七阶段。持久层设计仍须独立确定数据库列/复合 FK/追加保护与成功历史、Checklist 记录、实例更新的一致事务约束；若需增表或修订冻结语义，先记录 CR。

## 实际验证

Windows 11/Python 3.13：新增 8 项领域测试；后端 649 项无失败，2 项既有符号链接环境跳过。包含全部 36 阶段组合、五个合法相邻组合及完整快照边界。无 API/数据库/授权运行验收，因为没有入口/Migration；未测覆盖率与性能。

开发 wheel 构建并检查包含 `workflow/domain/history.py` PASS；SHA-256 `a0ee4f6e3978bfb4d95c034682bacbf659c1b40977d9f4a4c3eda52044ed6ee7`。不是正式安装包。

## 兼容、回滚与后续

无 Migration、公开 API、架构、新依赖或既有状态改变，升级无需动作；回滚为不使用新值对象，不删除历史。Server 2025 未运行，Debian 13 暂不验证。Gate 3/生产信任源/质量复验/完整 Workflow 尚未通过。

下一任务 WFL-02-A01-P02：追加迁移/Gate 与 Checklist 历史持久层设计、冻结差异登记；设计完成后单独实施 ORM/Migration/up/down/空库与有数据验证。不绕过实际 Gate/Owner 前置开放写 API。
