# PLG-01-A07：签名插件包元数据登记与验证结果原子 Owner 验收结果

- 状态：PASS_SCOPE_LIMITED
- 日期：2026-11-03
- 分支：feature/p51-a33-launcher-checksum-recovery
- 代码提交：`715c1646b2ba530e15998bb0cf63eddd7bf4a55f`；父子写入顺序修复：`894dd2d3f4c5fc6fc5acba5c29ec0f5a528b34c2`
- 验收运行：[GitHub Actions 41593955795](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41593955795)

## 结果

- GitHub hosted Windows Server 2025 全链路 13/13 jobs 成功；后端 3,909 项通过并构建 wheel，前端检查/build、Python embedded runtime、PG18/pgvector、父包组装、A35 handoff、A17 Edge/HTTPS/PG、A34 替换及显式人工恢复链路通过。
- PostgreSQL 18 临时数据库验证 Package 元数据、Manifest operations/dependencies、PASSED Verification 与 Audit 在同一调用方事务提交；Audit 失败整体回滚。
- 相同插件版本/相同摘要幂等；相同版本/不同摘要冲突；无效签名、兼容拒绝不写入。迁移 0223 空库升降级重升、有数据升级、历史保留、append-only/禁止 TRUNCATE 守卫通过。
- 首次PG集成曾暴露 parent 与子行 flush 次序错误。修复为在同一事务内先 flush Package parent，再插入子记录；没有提前提交。修复前后偏差、诊断和验证链均记录于 [CR-PLG-005](../changes/CR-PLG-005-package-registration-owner.md)。

## 边界与限制

- ZIP 内容仅在内存中校验，没有被持久化；未实现HTTP、异步Job、安装、启用、插件执行或撤销。
- 使用合成包、合成 Ed25519 key 和兼容策略；正式 signer trust 清单仍为空，生产导入继续失败关闭。
- 本轮只证明 hosted runner 上合成场景及 PostgreSQL 18 行为，不代表用户 Windows 11 实机、Windows Server 正式运行、正式信任、Gate 3、Pilot 或 Release 验收。
- 所有程序执行都在 GitHub hosted runner 的 D 盘临时工作区完成；未在用户本机或 C 盘运行。

## 变更清单

|类别|结果|
|---|---|
|Changed|签名插件包元数据原子登记 Owner 与 0223 append-only migration|
|Files|A07 服务、SQLAlchemy 仓储、0223 migration、单测、Migration validators、PG smoke verifier；见相关代码提交|
|Migration|新增 `20261103_0223`；down恢复闭写且保留记录；含历史数据时禁止破坏性降级|
|API|无公开HTTP/合同变更|
|Tests|hosted run 41593955795 全13 jobs成功；后端3,909项、PG18真实事务集成及全链路验证通过|
|Result|PASS_SCOPE_LIMITED|
|Known Issues|无公开导入/Job；包字节尚未持久化；正式信任清单空|
|Next|PLG-01-A08受控流式导入/异步验证Job编码前检查|
