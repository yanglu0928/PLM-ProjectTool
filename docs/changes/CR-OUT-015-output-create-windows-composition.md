# CR-OUT-015：OutputRequest Create HTTP接入显式Windows write composition

- 日期：2026-11-04
- 状态：P19编码前检查 PASS_WITH_LIMITATION；实施前置已记录
- 来源：CR-OUT-014/P18、CR-OUT-009/P12、CR-OUT-005固定Requirement source、CR-OUT-006/007 Template与Policy、CR-OUT-008/PLG-02 Plugin capability
- 基线：冻结API Contract V1 OUTPUT_REQUEST_CREATE；不改路由/DTO、架构、Schema或Migration

## 问题与证据

P12已有opt-in POST /api/v1/projects/{project_id}/output-requests router及严格字段校验；P01/P02已有Create owner、request/context存储、幂等、Audit、Job/Outbox；P05固定RequirementVersion adapter、P07/P09不可变Template/Policy registry、P11 Plugin capability投影均存在。P18已接通Cancel HTTP的显式Windows write composition，但production组合尚未创建/挂载Create router。

冻结API-03规定Create仅授权ProjectManager和ImplementationMember，并要求Session/CSRF、License、Idempotency、Audit。当前ProjectAuthorization缺OUTPUT_REQUEST_CREATE policy和production Access adapter。Plugin capability query需要外部可信签名Resolver；包内developer_keys.json的keys为空，故当前应返回trusted=false并拒绝Create，不得因此写Request/Job/Outbox/Audit/receipt，不得用测试密钥放宽。

## 实施边界

P19只接入冻结Create router到显式Windows include_secret_write组合：新增ProjectManager/ImplementationMember精确写策略和同事务Session/CSRF Access；复用License、Requirement fixed version owner+source adapter、内置Template/Policy、Plugin capability owner/package signer resolver、Output/Job/Outbox repositories、receipt/Audit与当前UOW。默认/login/只读App保持不挂载。不触碰P13 Read、P14 List或P18 Cancel，不改合同/数据库。

空publisher manifest是预期安全状态：即使路由装配成功，当前包仍因trusted=false拒绝创建并无持久副作用。Hosted用合成DB/身份，不写产品信任manifest、不执行插件或生成客户文件。

## 影响与回滚

- 错误挂载会意外公开写操作；使用router默认None且仅显式write注入，检查OpenAPI和HTTP。
- 权限不得扩展CustomerManager或CustomerMember；以冻结API03角色矩阵锁定PM与ImplementationMember。
- Policy allowlist不等同Plugin信任；缺可信签名key时operation capability必须false。
- 无Schema/Migration/API合同修改。回滚移除Create Access、factory、授权策略和显式写模式注入，保留P18 Cancel。

## 验收计划

1. 定向测试角色矩阵、Origin/CSRF/Session/License、默认404与显式write接线。
2. Hosted PG18.6合成来源和Plugin事实验证授权/写入边界；空可信key下断言无Output/Job/Outbox/Audit/receipt持久变化。
3. 后端全量/wheel、前端及父包/A17/A34/A35/A50 hosted回归、Secret检查；全程仅GitHub runner D盘临时环境。
4. 只按证据关闭P19；正式publisher、Output worker、Win11实机、Pilot/Gate/Release独立保留。

## 编码前检查结论

PASS_WITH_LIMITATION：依赖Owner/adapter可复用；缺少的仅为Create策略、Access和显式组合。trusted publisher manifest空且Worker尚无正式执行，必须保持Create fail closed/no-write边界。可按以上单一范围编码。
