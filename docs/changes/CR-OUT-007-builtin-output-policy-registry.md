# CR-OUT-007：内置Output Policy固定版本Registry

- 日期：2026-11-04
- 状态：编码前批准（CR-EXEC-002持续授权范围内）
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
