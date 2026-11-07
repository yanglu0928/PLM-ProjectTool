# OUT-01-A01-P03：Output固定来源、模板与策略解析器编码前检查

- 日期：2026-11-02
- 状态：PRECHECK_COMPLETE / IMPLEMENTATION_READY_WITH_CR-OUT-003（本切片不接公开HTTP、不执行插件）
- Phase/WBS：Phase 2 / OUT-01-A01-P03
- 前置：OUT-01-A01-P02 `PASS_SCOPE_LIMITED`；CR-OUT-002；API-03；DM-04；偏差先行记录 CR-OUT-003
- 运行约束：仅GitHub hosted Windows Server 2025 runner 的D盘临时目录及合成数据；禁止在用户本机/C盘执行

## 目标与单一问题

使用明确注入、可替换的可信 application Port 校验固定业务源版本、模板版本、输出策略和插件操作，产出不可变最小 ContextSnapshot。一个请求必须验证 source refs、template version、output policy 与 plugin operation 彼此受控且属于同一项目；不能接受任意UUID/字符串后直接排队。此项不增加HTTP路由、Plugin执行、Artifact或文件生成。

## 编码前检查

|检查|证据与结论|
|---|---|
|冻结API|API-03要求OutputRequest固定output type、template version、source version refs、policy、operation及最小Context；禁止动态current/latest，来源需同Project且按Review policy授权。|
|冻结模型|DM-04明确来源版本可为Requirement/Solution/Plan等不可变输入；快照只含已授权引用、顺序、参数及必要Evidence/Trace，不复制ORM/路径/Secret/无权正文。|
|前置实现|P02提供事务性创建 Owner、OutputContextResolverPort 与 ContextSnapshot 持久化；P02 hosted run 41413844603全13 jobs成功，范围仅合成PG/云端。|
|代码树审查|现有生产 Output 模块未实现模板/策略注册、Plugin模块或可信操作注册；Requirement/Solution/Plan各自的数据读取必须通过公开Port。PoC-08 manifest不等于生产信任。|
|偏差与边界|已先行建立 CR-OUT-003。P03 只新增可信 resolver 和显式 Port 的应用边界；定义缺失、未经授权或非固定版本均失败关闭。无持久注册实现时不得启用 resolver，也不得称已接入生产模板/插件。|
|涉及模块|Output application；测试仅覆盖该边界。不得查询别的模块私有 ORM。|
|涉及实体/API/权限|消费 OutputRequest、ResolvedOutputContext；固定API-03语义不变；通过现存 access、License 与各Source Port重新验证Project授权、审核状态。无API变化。|
|验收标准|全部引用准确匹配且不可变；Source同项目且符合审核/策略；Template/Policy/Operation版本与OutputType匹配；最小上下文采用字段白名单并受限大小；稳定fingerprint；缺失/越权/current/latest拒绝。定向和完整后端测试由GitHub hosted Windows runner执行。|
|风险及回退|当前无生产registry时，实际Create保持失败关闭。代码可通过移除resolver注册回退；本WBS无Schema/API/业务数据迁移。|

## 实施边界

按CR-OUT-003实现并验证可信解析组合器，不调用真实AI/网络/插件，不读取客户材料、不向外部服务发送数据，不把合成注册表当生产信任。后续注册表/插件安装与业务Port生产装配另按其自身WBS实施。
