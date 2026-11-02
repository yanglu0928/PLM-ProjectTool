# OUT-01-A01-P01：OutputRequest 与固定 Context 持久层编码前检查

- 日期：2026-11-02
- 状态：PASS_SCOPE_LIMITED（编码前检查、实现及托管验收完成；实施后流程偏差按CR-OUT-001追溯）
- 阶段：Phase 2；先完成 Windows 11 内部 Pilot 纵向链所缺 Output 起步层
- 本轮工作树：`feature/p51-a33-launcher-checksum-recovery`
- 依据：CR-EXEC-002、冻结的 API-03 Output 契约、DM-04 OutputRequest/OutputContextSnapshot 语义、当前 STATUS 与最新分支源码/迁移树

## 目标

只建立 OutputRequest 和不可变 OutputContextSnapshot 的 ORM/数据库持久结构，为后续应用 Owner、Job/Outbox、Plugin 执行、制品校验登记、HTTP/UI 和包内验收提供可追溯基础。该 WBS 不声称 Output 端到端可用。

## 编码前检查

|检查项|结论|
|---|---|
|当前阶段与依赖|PlanVersion 已有创建、验证、评审与冻结版本读取分片；本分支还没有 `modules/output` 或 Output 专用 migration。API-03 冻结了 OUT-01/OUT-02 及 OutputRequest/Artifact 操作契约。|
|只读源码证据|递归树检查 `apps/backend/src/plm_assistant/modules/` 未发现 output 模块；当前增量迁移止于 `20261026_0210`，未发现 OutputRequest/OutputContext 表迁移。|
|数据模型|OutputRequest 固定 output type、模板版本、来源版本集合、策略、插件操作、上下文快照指纹、Job/Execution 状态和幂等身份。OutputContextSnapshot 单独不可变，保存最小必要来源/顺序/模板参数/Evidence/Trace 引用，不含正文副本、绝对路径、Secret 或 ORM 对象。|
|API 与架构|不更改冻结 API-03、/api/v1、角色或模块边界；业务服务仅在后续任务经 OutputService 接线。当前只增加与冻结语义一致的实体和约束。|
|数据库兼容|新增递增 Alembic migration，不修改既有迁移；升级必须支持空库和现有 0210 数据库，降级只删除本 WBS 新增对象。列/约束需限定 Project 一致性、状态值、内容指纹长度及固定字段完整性。|
|本轮边界|不实现 HTTP、Job/Outbox、插件进程、文档发布/下载、Artifact、工作流、AI 或客户数据处理；不连接 Provider，不触碰用户业务数据。|
|验收|ORM metadata 与 migration 一致；定向单测；Hosted PostgreSQL 18 空库升级、从当前既有数据版本升级、降级/再升级；运行本分支规定的后端全量回归与 Secret 扫描；记录确切提交、Actions run 和限制。|
|安全/风险|源版本引用不得动态 current/latest；同 Project 与成员/权限校验后续 Owner 重做；Context 仅最小元数据快照。测试仅用合成数据。正式 License trust、安装身份、客户批准与 Windows 11 实机验收继续保持未通过。|
|回滚|仅回退本 WBS 新 migration 和 ORM/测试；若后续业务数据已依赖新表，先停止并按数据保留策略另做迁移，禁止静默删除。|
|本机资源|代码与验证仅提交到 GitHub 分支并由托管 Actions 执行；不在用户本机 C 盘安装依赖、运行测试或生成包。|

## 偏差记录

没有发现需要修改冻结模型/API 的不兼容点。本项是依照 DM-04/API-03 首次建立物理结构的计划内增量，不改写 Gate 2 冻结提交，也不新增跨域 Scope。若实现中遇到必须改变语义的冲突，先补 Change Request 与回滚/验证方案再编码。

## 通过条件

1. OutputRequest 固定输入与 ContextSnapshot 具备 Project 归属和不可变关联。
2. 非法 Scope、空输入快照、未知状态/类型、无效指纹被数据库约束拒绝。
3. ORM/Migration 一致，升级/降级与既有数据升级经托管 PostgreSQL 验证。
4. 只报告本 WBS 实际证据；不提升 Gate、Pilot 或 Release 状态。

## 下一项

完成本 Schema 切片后，单独前置检查 OutputRequest 同事务创建/幂等 Owner；不顺带接入 Plugin 或 Artifact。


## 编码后流程更正（2026-11-02）

初版前置检查把冻结 DB Schema V1 的首次 Output 物理扩展误判为无需 Change Request。复核后在继续修正测试前建立 `CR-OUT-001`，记录该基线扩展、流程偏差、风险与回滚。此前误分类作为历史保留，不覆盖；新代码尚未部署或触碰运行数据库。该 CR 完成之前不继续改变产品 schema/Owner 范围。

首次托管回归 run `41399398488`：后端 3,853 项中 1 项失败，原因是 `test_orm_metadata.py` 的显式历史元数据集合未纳入新 Output 表；前端/运行时构建前置与 A50 Edge job 成功，依赖后端测试的后续父包/A17工作按条件跳过。修正限定在测试清单，需在新完整托管 run 重验。该失败没有证明 PostgreSQL migration 升/降级，相关验收仍待。


## 第二次托管回归记录（2026-11-02）

run `41402169269` 中后端全量 3,853 项、前端、父包、A35及A17通过，A17为受限合成PASS_LIMITED。新增 PG18 migration 验证在 smoke harness 入口失败，错误为 `NameError: ROOT is not defined`，发生在调用 Alembic 测试脚本前；未执行迁移验证。本错误和修正范围已先记入 `CR-OUT-001`，随后才修复 harness 路径。不要把该 run 记作本 WBS migration 验收通过。


## 第三次托管迁移验证发现（2026-11-02）

run `41403739067` 已真实通过空库 head upgrade、Output revision downgrade 到 `20261026_0210`、再 upgrade head。旧版本升级夹具准备失败，因为旧迁移链已预置 `plt_maintenance_state` 单例，验证脚本重复插入冲突；未执行到 Output migration 的带数据升级断言。CR-OUT-001 已在继续改动前记录；修复限于读取旧版本已有合成记录并比较升级后值。


## 托管验收结果（2026-11-02）

结果：`OUT_01_A01_P01_PASS_SCOPE_LIMITED`。GitHub hosted PR run [41405621292](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41405621292) 全13 jobs成功，分支提交 `df7c79b3673e2825e70da379946dacbe3997d59a`。

1. 后端3,853项全量测试、backend wheel、前端测试/typecheck/build通过。
2. 托管 PostgreSQL 18.6 / pgvector 0.8.6：空库升级到head；降至`20261026_0210`并再次升级；既有合成维护哨兵升级后逐字段保持一致。
3. 父包临时生命周期、A34替换/失败隔离/显式手动恢复及A17 PlanVersion Edge/HTTPS/PG 29次API流程通过。
4. 对8个关联代码/验证文件进行目标式Secret pattern扫描/复核：无真实凭据或私钥；匹配项为测试合成哨兵。代码、依赖和临时数据在GitHub hosted Windows Server 2025的D盘runner目录。
5. 未安装产品、未启动服务/API、无客户数据、外部API或正式License信任。本项不含Windows 11设备、Output Owner/HTTP/Plugin/Artifact和端到端验证。

后续任务：`OUT-01-A01-P02` OutputRequest同事务创建/幂等Owner，需重新执行编码前检查；该Owner通过前新表保持写入关闭。

## 执行偏差追溯

编码前曾把冻结 DB Schema V1 首次实体扩展误判为计划内实现、无需CR。实施后在继续修正前建立`CR-OUT-001`，保留原始记录而不覆盖Gate 2基线。元数据清单遗漏、harness ROOT缺失和旧版本夹具重复插入也均逐项记录后修正。
