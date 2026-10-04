# HND-02-A04-A02：Action LIST/GET 内部读取 Owner

日期：2026-10-05。结论：`HND_02_A04_A02_ACTION_READ_OWNER_PASS`。下一项：`HND-02-A04-A03` Action cursor/HTTP。

## 实施结果

- 新增四类当前项目成员可用的`HND_ACTION_LIST`和`HND_ACTION_GET`只读策略，均锁定当前Project/Member事实；归档项目允许读取历史，写策略不受影响。
- LIST按`updated_at DESC, action_item_id DESC`返回有界摘要和完整下一位置；GET返回固定来源、输入规格、响应DocumentVersion引用、按purpose/ordinal排序的Evidence引用及当前状态最新事件。
- 读取顺序为License、当前Session、当前Project授权、资源归属和投影；跨项目/不存在/撤权统一隐藏，Session令牌不进入repr。
- 本项不写Audit或幂等收据，不展开无界历史，不读取Document路径、Evidence正文/定位或Trace端点。

## 验证

- Win11/PostgreSQL 18.6真实临时库验证通过：PM/IM/CustomerManager/CustomerMember、同时间戳稳定双页、摘要/详情/当前事件、跨项目/不存在/撤权拒绝、归档项目读取、License失败关闭以及Audit/收据/Action事件零写。
- 新增4项单元测试；相关权限合计11项通过；后端全量2651项通过/3跳过。
- 开发wheel构建与解包导入通过，SHA-256 `535c319eb4792114ee420bfe906a43109278f35633976e5112e08e29dc45e422`。

## 限制与回滚

无Migration、公开HTTP、cursor密钥、配置、依赖、网络或外发变化。停止装配读取Service即可回滚，历史不变。A03实现独立cursor/HTTP；Windows组合、前端、Handover Review/Workflow、真实资料质量与Gate 3仍待。
