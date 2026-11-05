# CR-OUT-029：输出成功终结与Artifact发布一致性Owner

- 日期：2026-11-05
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P33
- 状态：PRECHECK_COMPLETE；实施待按本CR进行
- 基线：Gate 2冻结的 OutputRequest、Job、PluginExecution、OutputArtifact V1；遵循CR-OUT-028/Migration 0232。
- 目的：在独立插件执行与文档暂存写入尚未接入前，建立内部、默认未装配的成功终结Owner，使已由受信验证器准备的引用和四项受控校验结果能够以同一事务完成Artifact可用、Request成功、Job成功及Audit。

## 编码前检查

源码确认：P29/P30/P31已有按当前fencing claim推进Output的Start/Failure/Retry Owner；Output失败/重试事务均按Output行后Jobs claim顺序运行。Jobs已有通用`finish`接口，但它本身不验证Output Artifact/Request同一项目/执行/内容引用，单独调用会留下Job与业务聚合不一致风险。P32已提供Artifact Root、Validation child、 AVAILABLE 数据库不变量与写关闭守卫。PluginExecution的持久化与状态模型已存在，但真实插件Worker/JSON-RPC发布链和Document本地文件原子提升并未因此成为可用能力。

## 实施范围

- 增加只接受当前OUTPUT_GENERATE有效claim的内部成功终结Owner及明确的数据端口；事务顺序固定为 Output → Jobs。
- 仅接受同项目、同OutputRequest、当前PluginExecution与 GENERATED_ARTIFACT DocumentVersion/FileObject一致的受控facts；四个验证类别均须以安全代码结果PASSED。
- 一个事务中追加验证历史、推进Artifact到AVAILABLE、OutputRequest到SUCCEEDED、Jobs Lease/Attempt/Job到SUCCEEDED并写SYSTEM Audit；任一步失败整笔回滚。重复提交幂等，旧worker/fencing token、错误项目/请求/执行/文件引用、缺项验证和Audit失败均拒绝。
- 默认不挂载HTTP，不改变冻结API或Schema；不添加Worker轮询，不写本地文件，不启动插件子进程，不声称正式Publisher信任或开放生产输出。

## 偏差、风险和回退

- 偏差：Job通用finish缺少业务成功证明。以Output-owned协调端口调用Jobs-owned同事务完成方法，不复用Output业务逻辑进入Jobs，也不改变Lock方向。
- 风险：事务结束与文件系统提交存在不一致窗口；本WBS只接收已存在的DocumentVersion/FileObject固定引用，不承担文件写入。后续必须由Storage/Document发布任务按ADR-008完成STAGED、同文件系统原子提升、Hash复验、补偿和恢复一致性验收。
- 回退：纯应用层新增Owner/端口/Repository/test可撤回；不需Migration。所有写操作仍仅合成测试数据库，且默认装配关闭。
- 验收：Hosted全量后端、wheel、前端/build与隔离PG18真实事务正反例；项目隔离、当前lease/fencing、四项验证、Artifact/Request/Job三方原子性、Audit回滚和幂等均通过后方可标记PASS_SCOPE_LIMITED。

## 编码前检查结论

PASS_WITH_LIMITATION：本地源码/基线通过GitHub branch只读核对；新增成功终结Owner可与冻结模型兼容且不需要Schema/API变更。P25 initdb失败不影响单独PG18 verifier。所有程序和测试继续仅在GitHub hosted runner的D:临时环境运行。


## 首轮 P33 偏差登记（修复前，2026-11-05）

Hosted run [41992151148](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41992151148) 的新增P33应用层测试发现审计契约接线错误：`AuditEventDraft.outcome`只允许`SUCCESS/DENIED/FAILED`，Owner传入了`SUCCEEDED`。失败在SYSTEM AuditDraft构造时发生，事务上下文回滚了Output、Artifact、Job、Lease及Audit，无持久化副作用；其余后端4,057项通过，新增P33用例1项失败，前端/build与runner路径检查通过。此次验证不代表P33通过。

修复方案：状态字段继续使用业务终态`SUCCEEDED`；仅Audit outcome改为`SUCCESS`，并同步测试期望。不得改Audit枚举或公开API，不扩大范围。重跑全量Hosted workflow并确认回滚断言仍通过。


## P33 PG18 verifier 首轮偏差登记（修复前，2026-11-05）

Hosted run [41995972249](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41995972249) 后端全量/wheel、前端/build、PG sidecar、父包组装及P24/A50均成功；父包PG18 smoke运行到P33 verifier入口时，在合成fixture SQL字面量包含未转义JSON双引号处出现Python `SyntaxError`，P33数据库及Owner验收代码尚未执行。不能视为P33失败或通过。

修复计划：将ContextSnapshot/OutputRequest的source refs移为参数化JSONB输入，避免测试SQL字符串转义；只改验证器fixture，不改Owner/Repository/Schema。随后重跑完整Hosted全链和P33事务验收。


## P33 PG18 fixture前置状态偏差登记（修复前，2026-11-05）

Hosted run [41997886517](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41997886517) 的P33 verifier已通过脚本编译、全量后端/wheel、前端/build、PG sidecar、父包组装及前序PG verifiers；在P33第一次调用成功Owner时，应用层拒绝candidate。根因是verifier直接插入 `request_state='GENERATING'`，但未模拟 P29 状态转移必须递增的 `lock_version=1`（默认值仍为0）。Owner在任何发布/终结写入前正确失败关闭，事务无业务状态变更；这属于测试夹具与冻结前置状态不一致，不能视为Owner缺陷或P33通过。

修复计划：仅在合成OutputRequest fixture中显式设`lock_version=1`，符合当前有效P29生成启动事实；保留其他SQL/Owner/Schema不变，重跑全链与PG18成功/回滚断言。


## P33 PG18成功路径资格拒绝（修复前，2026-11-05）

Hosted run [41999961492](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41999961492) 的P33 verifier编译、全量后端/wheel、前端/build、PG18 sidecar重建、嵌入式Python及Windows父包组装、A17候选投影、A35、A50和P24通过。父包PG18 smoke启动临时库并完成迁移，随后预期成功的Owner调用返回 `OUTPUT_COMPLETION_NOT_ELIGIBLE`，本轮尚未提交Artifact/验证记录/Output/Job/Audit写入；P33暂不能通过。原因尚未定位，不能先验归咎Owner或测试夹具。P25仍独立在initdb以3221225781/0xC0000135退出并保留无法判定停止状态的D盘临时PG数据，属于已知独立阻断。

修复计划：只在一次性verifier数据库增加无客户数据的发布前置引用谓词检查，逐项确认PluginExecution、FileObject、Document、DocumentVersion符合Owner查询条件；输出不含敏感数据的布尔断言/缺失阶段，定位是fixture或Owner predicate。若夹具与既有持久化契约不一致，只修fixture并重跑；若现有Owner谓词与冻结模型不一致，才调整Owner并补单测。无条件清理不确定状态数据，当前runner已结束，不触及本机。修复后重跑完整hosted验证。


## P33资格诊断输出未穿透包装器（修复前，2026-11-05）

Hosted run [42002678699](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42002678699) 后端全量/wheel、前端/build、PG18 sidecar、嵌入式运行时、父包组装、A17/A35/A50/P24均通过；P33隔离PG18 verifier仍在预期成功Owner调用处返回 `OUTPUT_COMPLETION_NOT_ELIGIBLE`，事务失败关闭。此次新增资格谓词检查写到子进程stdout，但父包smoke包装器仅把子进程stderr尾段放入失败日志，故确切谓词结果未进入可见验收日志。没有Owner/数据库变更，P33仍未通过。P25仍独立因initdb退出3221225781/0xC0000135，未启动HTTP/Edge。

修复计划：只将同一无敏感布尔资格诊断输出到stderr，使现有父包装器能保留原因；不改任何业务Owner/Repository、Schema或数据。再次hosted验收，根据谓词结果再判断只修夹具或Owner条件；保留Audit失败全回滚、错Document拒绝和成功事务三组断言。


## P33当前Job Claim夹具trace_id不一致（修复前，2026-11-05）

Hosted run [42004860834](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42004860834) 的完整后端/wheel、前端/build、PG18 sidecar、嵌入式运行时、Windows父包、A17/A35/A50/P24均通过；P33 PG18 verifier报告PluginExecution、FileObject、Document、DocumentVersion四项精确Repository资格谓词均为true，但Owner仍在当前claim比较处拒绝。源码定位为 `Jobs.check_output_claim(...)` 返回值与调用claim要求全字段相同。verifier的合成Job `trace_id` 使用了独立uuid `trace_text`，而OutputRequest与调用claim使用另一个trace uuid，故属于夹具与P29一致性前置不匹配；Owner正确失败关闭，尚无成功提交，P33未通过。P25继续独立因initdb 0xC0000135受阻。

修复计划：仅令合成Job `trace_id` 与同一合成OutputRequest/Claim的 `data["trace"]` 一致；保留其余模型、Owner/Repository及数据库不变。加强verifier断言，确保Audit失败场景确实到达Audit端口，随后验证错Document拒绝、成功三方原子完成、四项validation、Audit同事务及全量测试。继续仅GitHub hosted runner D:。
