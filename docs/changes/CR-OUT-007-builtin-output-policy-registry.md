# CR-OUT-007：内置Output Policy固定版本Registry

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED（实现与托管验收完成）
- WBS：OUT-01-A01-P09
- 来源：P06/P07基线核查、冻结API-03/DM-04/DB Schema V1、现有Resolver DTO/Port、CR-OUT-004/006

## 问题与依据

Output resolver要求Policy固定允许的模板版本、输出类型、插件操作、来源审核状态、来源字段白名单和Context上限。当前只有OutputPolicyVersion DTO/Port，没有Policy Owner/Registry。冻结Output仅有Request/Artifact两个Root，API-03无Policy管理CRUD；本项目已选择内置固定目录，不新增客户DB表/API/Migration。

## 决定与边界

- P09增加只读、版本化内置Policy Registry，固定ref对应现有OutputPolicyVersion DTO；不得基于当前模板或可变配置动态放宽规则。
- 唯一策略只允许P07固定DOCX模板、RequirementVersion的APPROVED来源；字段限title/statement/acceptance_criteria，最大4个来源和8192字节Context。word.generate仅是策略允许操作标签，不代表Operation已经安装/启用或受信任；缺真实Plugin Operation Registry时Resolver仍必须失败关闭。
- 不设置跨业务通用Policy、不接生产Resolver或OutputRequest、不生成文件、不运行插件、不开放用户编辑，不扩大数据外发或客户数据访问范围。
- 不改变冻结Architecture/Data Model/DB Schema/API，不新增依赖/Migration。未来增加模板/来源/操作时须新增Policy版本，历史版本保持稳定。

## 验收、风险、回滚

- 单测覆盖固定ref精确读取、字段白名单、审核态/模板/类型/操作约束、大小限制、未知/重复/畸形策略拒绝、目录不可变。
- A17 packaged runtime smoke验证PolicyRegistry与Wheel随包一致并输出P09 marker；完整GitHub hosted workflow含后端全量/wheel、前端、PG18基础、父包、A35/A17/A34。
- 风险：静态Policy过窄可能限制功能；安全约束采取只能由新增受审代码版本调整，不接受运行时任意放宽。
- 回滚移除新增Registry适配/条目，Resolver缺Policy继续失败关闭，不改数据/冻结基线。

## 追溯

- P08核查：docs/progress/out-01-a01-p08-policy-registry-precheck.md
- P09结果：待实现与hosted验收后补录。


## 实现提交（云端验收待完成，2026-11-04）

- 新增固定ref策略Registry，边界固定为DOCX/P07模板/RequirementVersion APPROVED，字段title/statement/acceptance_criteria，最多4来源与8192字节。策略内word.generate只是allowlist标签；单测中的enabled/trusted operation为synthetic依赖，不表示真实信任。
- 单测覆盖未知/扩大策略拒绝、Registry/字段映射不可变及Resolver最小字段投影；A17 packaged flow新增P09 marker。
- 无Migration/API变化。定向/后端全量、wheel及hosted父包/A17/A34待本提交验收。


## 首轮托管验收偏差（2026-11-04）

- GitHub hosted run [41692180197](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41692180197) 在后端测试中1项失败，导致后续wheel/父包/A17/A34依赖job跳过。
- 失败根因是新增测试对空Policy目录断言通用文本“catalog is invalid”，而实现对空目录返回更精确的“builtin output policy catalog is empty”；没有证据表明Registry接受非法数据或产品逻辑失效。
- 修正方案：仅更正测试预期为目录为空错误；重复/扩大策略继续断言catalog invalid。然后在GitHub hosted runner重跑定向、后端全量/wheel及完整父包链。修改前不关闭P09，不降低验收项。


## 修正与最终验收（2026-11-04）

- 首轮run [41692180197](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41692180197) 的唯一失败是新增测试对空目录错误文本断言错误；修正只改测试预期，未改变产品逻辑。偏差及计划在实施前已补录本CR。
- 修正提交ac7cae27的run [41693364068](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41693364068) 全13/13 jobs成功；后端全量/wheel、前端、PG18/pgvector、父包/A35、临时PG、A17和A34全部通过。A17 Artifact含marker `OUT_01_A01_P09_BUILTIN_POLICY_REGISTRY_PASS`。
- 结论PASS_SCOPE_LIMITED：只验证合成固定策略。没有Production Plugin Operation enabled/trusted facts，无Output Create、渲染或Artifact发布，也没有Win11实机/Pilot/Gate/正式Release验收。
