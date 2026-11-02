# OUT-01-A01-P03：Output固定来源、模板与策略解析器编码前检查

- 日期：2026-11-02
- 状态：PRECHECK_COMPLETE / READY_TO_IMPLEMENT（仅可信解析与最小Context构建；不接公开HTTP、不执行插件）
- Phase/WBS：Phase 2 / OUT-01-A01-P03
- 前置：OUT-01-A01-P02 `PASS_SCOPE_LIMITED`；CR-OUT-002；API-03；DM-04
- 运行约束：后续仅GitHub hosted Windows Server 2025 runner 的D盘临时目录及合成PG18；禁止在用户本机C盘执行

## 目标与单一问题

用项目内真实且固定版本的业务来源验证器替换P02合成resolver边界，产出可持久化的最小ContextSnapshot。一次请求必须验证 source refs、template version、output policy 与 plugin operation 彼此受控且属于同一项目；不能接受任意UUID/字符串后直接排队。此项不增加HTTP路由、Plugin执行、Artifact或文件生成。

## 编码前检查

|检查|证据与结论|
|---|---|
|冻结API|API-03要求OutputRequest固定output type、template version、source version refs、policy、operation及最小Context；禁止动态current/latest，来源需同Project且按Review policy授权。|
|冻结模型|DM-04明确来源版本可为Requirement/Solution/Plan等不可变输入；快照只含已授权引用、顺序、参数及必要Evidence/Trace，不复制ORM/路径/Secret/无权正文。|
|当前实现|P02仅接收注入ResolverPort；当前集成验收使用synthetic resolver/access/license替身，不证明真实项目来源、模板策略或用户授权；公开Router尚未接入。|
|静态边界|Output模块现有物理模型只有OutputRequest/ContextSnapshot；尚无OutputTemplate/Policy registry owner。Source-version读取需走其源模块授权应用Port，不得由Output模块直接查询其它模块私有ORM。|
|风险与处理|模板/策略身份当前只有ref字段，没有被任何现有Output registry约束。实施前须确认既有能力库/Plugin manifest是否已提供可复用的不可变版本及操作授权事实；若不存在，先按持续授权记录CR，决定最小新增Schema/迁移与回滚，再编码。不得把合成注册表称为生产信任。|
|验证计划|真实SQL读固定版本归属/状态与同Project隔离；未批准/缺版本/跨项目/动态版本拒绝；Context最小化与fingerprint稳定；不存在外部AI/API调用；临时PG迁移及回滚；后端定向+全量、Secret检查及父包CI。|

## 实施边界与建议

优先复用已存在的Requirement/Solution/Plan固定版本只读应用Port和模板/操作注册；所有依赖以port注入，跨模块只调用公开application contracts。遇到模板/策略注册事实缺失时先记录CR-OUT-003，保留CR-OUT-002/P02历史与Gate2冻结基线；首轮只实现明确可验证的受支持来源集合并对其它来源失败关闭。不得调用真实AI、插件、外部服务或客户资料。
