# CR-OUT-015：OutputRequest Create HTTP接入显式Windows write composition

- 日期：2026-11-04
- 状态：P19 PASS_SCOPE_LIMITED；P20为下一项
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


## 执行偏差记录（首次Hosted验收）

- Run [41813995345](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41813995345)：P51-A32 projection、前端、PG18/pgvector、Python embed、A50通过；后端全量在4,018项中1项失败，导致后续依赖父包/A17/A34/A35作业跳过。
- 失败：新组合单元测试断言了不存在的 `OutputRequestService._guard`；实现实际将依赖保存为 `_license`。这是测试字段名错误，非运行时实现异常。
- 修复：仅将组合测试断言改为检查 `_license`；再跑完整云端工作流（含4,000+后端测试、PostgreSQL父包smoke、A17/A34/A35/A50）。本失败及重验完成前不关闭P19。


## P19执行与验收结果

- 实施：新增 `OUTPUT_REQUEST_CREATE` 项目权限策略与同事务Session/CSRF Access；将既有Create router、Requirement固定版本读取、内置Template/Policy、Plugin capability/signature trust、Output/Job/Outbox、Audit/幂等组合为显式Windows write router。默认/login/只读App未挂载。无API/Schema/Migration改动。
- 定向授权与组合测试通过；首次全量run中的单一错误断言已按上文记录修正。
- Run [41830014604](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41830014604)：13/13 jobs成功；backend 4,018 tests/wheel、frontend tests/typecheck/build、PG18.6/pgvector、父包、A17/A34/A35/A50通过。
- PG18.6合成HTTP验证通过：ProjectManager与ImplementationMember因包内发布者manifest为空而得到失败关闭响应；CustomerManager被拒绝。对Output、Job、Outbox、Audit、幂等表的请求前后计数完全一致。默认应用无Create route。宿主数据库/Session/License为合成，未联系外部API/插件，未生成文件。
- 非发行父包20,201项；内部SHA-256 `7197e04bb47982c20f9c8988f12a1186a0f5e11b8bd1a6e80c093f12803fd7bd`。未进行Windows 11本机安装/实测。
- 结论：`PASS_SCOPE_LIMITED`。正式publisher信任、Output Worker、License信任、Win11实机及Gate/Pilot/Release不由本项通过。
