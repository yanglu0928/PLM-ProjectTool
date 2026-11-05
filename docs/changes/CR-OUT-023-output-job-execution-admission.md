# CR-OUT-023：Output Job 执行前请求/快照绑定与当前能力复验

- 日期：2026-11-05
- 来源：OUT-01-A01-P26按CR-OUT-022完成限界验收后，继续补齐Output消费安全边界
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P27
- 类型：Output内部只读执行准入校验；不修改冻结基线、Schema、Migration、公开API或默认运行时挂载
- 状态：已完成编码前检查，PASS_WITH_LIMITATION；允许实施准入Owner及其证据，不允许执行插件/生成文件

## 现状证据

- P26已证明Jobs通用claim不会取走精确的 output/OUTPUT_GENERATE，Output专属claim保持租约/fencing；目前没有Output生成Worker或插件执行入口。
- Jobs enqueue在同事务写入Job的 output_request_id/context_snapshot_id，OutputRequest保存 job_ref、project_id、context_snapshot_id、plugin_operation；ContextSnapshot保存 project_id、来源版本、context_payload及SHA-256 fingerprint。
- 创建时 TrustedOutputContextResolver 会检查模板/策略、来源及插件能力；PluginOperationCapabilityReader可读取当前 enabled/trusted及允许的输出类型。创建时检查不能替代未来执行时复验，插件可在入队后被停用或信任状态变化。
- P26专项验证使用合成的随机Request/Snapshot引用来测claim隔离，并不验证这些引用之间的业务绑定。

## 决策与实施

新增Output-owned的只读准入Owner/Repository，在未来任何生成/插件副作用前可复用。它必须在一个Output事务中验证：
1. 输入Claim类型、Output Generate类型、Project与payload refs格式有效；
2. 同一Project下OutputRequest存在且其 job_ref、context_snapshot_id与Claim payload精确一致，request_state仍允许开始；
3. ContextSnapshot存在、Project一致，来源版本引用及fingerprint与OutputRequest/上下文一致，重新计算的fingerprint相符；
4. 当前Plugin capability唯一、enabled、trusted，且支持该request的output_type；缺失、异常、撤销或不匹配均失败关闭。
5. 成功仅返回repr隐藏的最小准入事实，不返回context正文、不改业务状态，不生成文件、不调用插件。准入结果不替代真实Worker执行前的活动租约/fencing复验；该接口本身不得接入或启动Worker。

## 风险、恢复与验证

- 风险：错误绑定、过期请求或撤销的Plugin能力若未在副作用前复查，可能造成跨请求生成或绕过停用。本次通过同事务绑定检查与当前能力投影拒绝此类准入；不声称消除准入之后的租约过期竞态。
- 回滚：撤回新增Owner/Repository及测试即可；不需要数据迁移。无公开接口、运行时挂载或消费者变更。
- 验证计划：输入/引用/项目/状态/fingerprint/能力缺失或撤销单测失败关闭；Hosted PG18 synthetic rows验证精确绑定通过及不一致拒绝；后端、前端、父包流水线复验。用户本机/C盘不运行代码，所有运行使用GitHub hosted runner D盘临时区。
- 隐私：不读客户业务数据；只使用由CI创建的合成行，不调外部API、不执行插件、不生成文件、不使用正式密钥。


## 编码中复核发现（修复前记录）

- 在首次P27 hosted验证完成前的代码对照中，发现初版准入Owner仅校验ContextSnapshot自身fingerprint，未重算OutputRequest在创建时使用的总input_fingerprint（该指纹还覆盖Project、Output类型、模板、来源、策略与Plugin operation）。若不补此项，持久化请求内容与其总输入指纹之间仍存在未验证绑定。
- 修复方案：按OutputRequestService创建时的canonical payload结构重算总指纹，并与OutputRequest.input_fingerprint逐字节比较；把错配加入单测和D盘hosted PostgreSQL拒绝用例。先登记本偏差再修，不更改Schema/API/业务状态或数据。


## 单测发现配置偏差（修复前记录）

- 第一次P27全链候选run [41935554958](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41935554958) 的后端job仍显示原4,023 tests。检查workflow后确认后端使用 `python -m unittest discover -s tests -p "test_*.py"`；新增文件最初使用pytest函数，虽被发现文件名匹配，但没有TestCase类，因此其函数用例未实际执行。
- 修正计划：将同一边界用例改写为 `unittest.TestCase` 并使用 subTest；新的hosted run必须显示后端测试数上升，且PG专项summary通过，之后才可评估P27。该轮不视为P27单测验收。


## Hosted PostgreSQL 验证偏差（修复前记录）

- Run [41936428745](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41936428745) 的后端回归通过，新增unittest已纳入；P27 PG smoke在最后的fingerprint篡改负例触发数据库不可变触发器“Output context snapshots are immutable”，验证器因此失败。这证明数据库层不变量有效，不能通过直接更新快照来制造负例。
- 修正方案：移除PG脚本对不可变ContextSnapshot的UPDATE及对应SQL依赖；保留对错绑snapshot引用、插件禁用/不可信/输出类型不匹配的真实PG拒绝验证，fingerprint篡改保持纯单测验证。重跑 hosted 全链；不放宽数据库约束。


## hosted 复验与结论（2026-11-05）

- Run [41940381378](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41940381378) 的后端全量4,027 tests/wheel、前端测试/typecheck/build、PG18/pgvector构建及父包组装成功；A35成功。父包PG smoke中P26 claim与本P27准入均返回PASS_SCOPE_LIMITED。
- P27 PG证据：正确的 synthetic Job/OutputRequest/ContextSnapshot绑定通过；错绑Snapshot被拒绝；当前Plugin operation disabled、untrusted或不支持DOCX均被拒绝。返回对象不含Context payload；客户数据、插件执行、文件生成、外部API均为false/0，runner_drive=D:。
- 单测真实由unittest discover执行，后端报告4027 tests。Snapshot指纹破坏用纯单测覆盖；PG验收服从数据库不可变触发器，未修改Snapshot数据。
- **结论：OUT-01-A01-P27 = PASS_SCOPE_LIMITED。** 结果文档：docs/progress/out-01-a01-p27-output-job-admission-result.md。Run内P25仍独立失败于initdb 0xC0000135，真实HTTP/Edge未执行；Pilot/Gate/Release结论未变化。
- 下一WBS为Output Worker副作用前的活动租约/fencing证明及状态推进Owner编码前检查。该准入Owner不启动Worker，不代表正式Publisher信任或可执行插件。
