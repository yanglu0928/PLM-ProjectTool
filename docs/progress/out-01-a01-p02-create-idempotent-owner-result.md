# OUT-01-A01-P02 结果：OutputRequest 同事务创建与幂等 Owner

- 日期：2026-11-02
- 状态：PASS_SCOPE_LIMITED
- 分支：feature/p51-a33-launcher-checksum-recovery
- CR：CR-OUT-002
- 验证：GitHub hosted PR run [41413844603](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41413844603)，全13 jobs success；验证提交 `d1a28f531a7b2291f997b156e38818f83f77f8d5`

## 实现

- 新增内部 `OutputRequestService`、SQL repository、Jobs-owned Output Job/Outbox port与adapter。
- 单一 UOW 中持久化Project-scoped ContextSnapshot、OutputRequest、Job、Outbox、Audit和通用幂等receipt；调用端不自行提交部分写入。
- 通过P02注入的授权/License/解析port工作；鉴权与License对重放仍重新检查。
- PostgreSQL transaction advisory lock使相同generation并发请求合并；原始幂等Key只以SHA-256摘要进入OutputRequest唯一键。
- Migration `20261102_0221`开放Owner INSERT/UPDATE/DELETE拒绝触发器，保留NO-TRUNCATE与ContextSnapshot UPDATE/DELETE不可变触发器，并给job_ref添加NO ACTION外键。降级恢复写拒绝trigger及移除外键，不删除业务历史。
- 未挂公开HTTP，未执行插件/Artifact/文件输出，不调用外部API。

## 验收

GitHub托管Windows Server 2025 / D盘临时目录；PostgreSQL 18.6、pgvector 0.8.6；全程合成身份和业务输入，无客户数据、无付款/服务安装/真实信任：

- 后端完整测试和wheel、前端测试/typecheck/build通过。
- 空库/历史库迁移通过；0221→0220→0221的含历史往返后，Context、Request、Job、Outbox、Audit、receipt的行身份、关联和Key摘要未变化。
- 同Key重复返回相同Request/Job；不同Key相同generation并发调用合并为单一Request/Job/Outbox/Audit；异载荷复用同Key返回冲突。
- Audit注入故障时Output/Job/Outbox/receipt整体回滚；未授权调用不产生写入。
- ContextSnapshot UPDATE和DELETE被数据库拒绝；OutputRequest不落原始幂等Key。
- 同run parent package、A17 PlanVersion Edge/HTTPS/PG、A34显式恢复回归通过。

## 偏差记录

实施期间先发现并在CR-OUT-002记录后修正：
1. Revision命名最初使用次日日期，改为当日`20261102_0221`。
2. 最初将随机Request UUID写入Output幂等字段，改为稳定Key摘要。
3. 移除拒绝写trigger可能开放快照变更，补充不可变trigger及回归。
4. 首轮验收没有含历史的迁移往返，补充后实测通过。
5. 第二轮 hosted harness将换行误写为字面`\\n`导致SyntaxError；修复后全链复验通过。

## 限制

此为内部Owner和合成PG证据，不能证明生产Session/License/项目成员装配、真实业务来源/template/policy解析、HTTP、Windows 11实机、客户数据或正式可用程序包。Gate 3、Pilot和正式Release状态保持NOT_READY。
