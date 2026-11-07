# OUT-01-A01-P01：OutputRequest 与 Context 持久层验收结果

- 日期：2026-11-02
- 状态：PASS_SCOPE_LIMITED
- 变更记录：CR-OUT-001（VERIFIED，限本 schema foundation）
- PR：[#61](https://github.com/yanglu0928/PLM-ProjectTool/pull/61)
- 分支提交：`df7c79b3673e2825e70da379946dacbe3997d59a`
- GitHub Actions：[run 41405621292](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41405621292)，13/13 jobs成功；PR merge检查提交 `3fec549457eea2a9567582be623d389b932d24be`

## 交付内容

- 新增 `plm.out_context_snapshots` 与 `plm.out_output_requests` ORM表。
- 新增 Alembic revision `20261102_0220`，从既有 `20261026_0210` 递增。
- 保持Project复合归属、固定引用/快照指纹、状态和输出格式约束、代次及项目内幂等身份约束。
- 增量通过CR-OUT-001追溯；原Gate 2冻结提交 `64cdf09` 未改写。

## 验证证据

|验证|结果|
|---|---|
|后端全量测试 / wheel|3,853项通过 / 构建通过|
|前端测试、typecheck、production build|通过|
|PostgreSQL 18.6 / pgvector 0.8.6 空库升级|通过|
|空库降至 `20261026_0210` 并重升|通过|
|旧版本合成哨兵数据升级后逐字段比对|通过|
|父包临时提取与PG生命周期|通过|
|A34隔离替换、显式手动恢复|PASS_LIMITED|
|A17 PlanVersion Edge/HTTPS/PG|29次合成API调用通过|
|关联8个代码/验证文件Secret pattern检查|未发现真实凭据/私钥；命中内容仅为测试合成哨兵|

父包SHA-256：`a3062a6311d20c6d63f93dea6ce13b58136b8c0c45115e93345d45708cb3e1ea`（20,126文件）。A17候选SHA-256：`d2215bd8b57ede09bb956c94659a68872cc82dc86cde45ff60fc13162d63ffe5`（20,120文件）。

## 限制

代码、依赖、测试、解包和临时数据库均在GitHub托管Windows Server 2025 runner运行，工作目录及TEMP位于D盘；未在用户本机C盘运行，未访问生产数据库，临时数据库随job清理。无客户数据、外部API调用、正式License trust、产品服务/API启动或安装。

仅关闭持久层WBS。此证据不代表Windows 11设备运行、Output写Owner、HTTP、Plugin、Artifact、端到端链路、Gate 3、Pilot或正式Release通过。

## 下一WBS

`OUT-01-A01-P02`：先审查事务、Project/权限绑定及幂等边界，再实现OutputRequest创建Owner；未完成前不得开放新表写入或扩展至Plugin/Artifact/公开HTTP。
