# OUT-01-A01-P34A 实施候选与托管验证结果

- 日期：2026-11-05
- 结论：代码候选已实现；backend全量测试通过；P34A尚未通过（隔离PG18专项调用缺失）
- Change Request：CR-OUT-031
- 分支：feature/p51-a33-launcher-checksum-recovery（PR #61；base main）
- 关键提交：f703c593（Owner/Repository）、116afed26（定向单测）、180e2b503/391789643（校验与SYSTEM审计请求者归属修订）
- Hosted run：[42030014722](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42030014722)
- 用户本机/C盘未运行代码；项目程序和测试仅GitHub hosted Windows D盘

## 已实现

- 新增document.application中的OutputGeneratedDocumentVersionOwner与SqlAlchemyOutputGeneratedDocumentVersionRepository。
- 在一个UOW中按请求行→Job fence→Execution→FileObject→Document顺序核验项目、CURRENT Execution、attempt、最终locator、可用FileObject内容摘要与GENERATED_ARTIFACT Document。
- 基于Execution+FileObject生成稳定DocumentVersion标识，插入不可变AVAILABLE版本和OUTPUT_GENERATION source ref，按冻结触发器顺序推进Document.latest_version_ref，并同事务写SYSTEM Audit（original_actor_id保留Output请求人）。
- 不执行Storage提升、不创建Document/FileObject、不插Artifact、不结束Job、不接API/Worker/默认组合。

## 验证证据与缺口

run 42030014722：backend全量测试与wheel成功；frontend/build、PG18 sidecar、父包组装、父包既有PG18/pgvector smoke、A17、A34、A35、P24及A50成功。定向fake-port单测覆盖当前claim/事务提交、Request锁先于Job检查、无效Execution拒绝及Audit异常不提交。

仍未证明SQLAlchemy Repository在真实隔离PostgreSQL 18中成功建版本、触发器/复合关系/source ref/Audit持久化、exact replay、旧fencing或Audit失败回滚；父包PG smoke本轮运行的是P33旧fixture，并未调用P34A。下一步把P33 smoke fixture调整为无DocumentVersion初态，先执行P34A提交/精确重放，再执行P33终结Owner，并在GitHub hosted PG18复验。P34A在专项PG18验收通过前不记PASS。

P25 job本轮独立失败：同run父包initdb差异对照仍exit 3221225781/0xC0000135、没有创建数据库目录，未执行真实Output HTTP/Edge；其他列出的工作流job成功。此阻塞不改变P34A代码证据，也不视作P25、Pilot、Gate或Release通过。