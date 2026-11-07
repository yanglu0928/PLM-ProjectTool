# OUT-01-A01-P08：Output Policy固定版本Registry编码前核查

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED（Owner/冻结边界盘点完成，未编码）
- WBS：OUT-01-A01-P08
- 依据：CR-OUT-004/006、P07 PASS_SCOPE_LIMITED、冻结API-03/DM-04/DB Schema V1

## 问题

TrustedOutputContextResolver要求明确、固定版本OutputPolicy。缺失Policy时必须拒绝；不得以空策略、默认宽松策略或AI建议替代。

## 编码前检查

- 检查冻结Data Model/DB Schema/API和当前Output ORM/Resolver，确定是否已有Policy Aggregate Root/表/API；如无，评估内置策略目录是否可满足当前只读内部模板边界。
- 检查Output Source projection/Policy白名单的交集，不能从不必要读取字段扩展允许范围。
- 对齐唯一P07模板ref、DOCX输出类型、支持的已授权来源和实际插件Operation Registry状态；Policy的allowed operation只是必要条件，不是信任/启用证明。
- 固定review状态、每次来源数量/Context字节上限、不可变版本Ref和未知值fail-closed语义。
- 确认不新增用户可编辑策略、不接生产OutputResolver、不外发数据、不新增DB/API/Migration；任何冻结基线变动须另建Change Request并保留原冻结版本。
- 验收在GitHub hosted runner执行；A17 packaged runtime marker验证随包，后端与完整父包链全绿后才关闭。

## 下一步

完成上述Owner/基线核查后更新P08结论；若选择内置目录，建立P09编码前CR并写明Allowlist、风险、回滚及托管验证计划。


## 源码与冻结基线盘点结果（2026-11-04）

- Data Model V1及DB Schema V1只有OutputRequest/OutputArtifact两个Output Root；当前ORM仅有请求与ContextSnapshot。API-03仅在Create固定output_policy_ref，没有Policy管理端点。
- Output resolver要求严格的OutputPolicyVersion，并在缺Policy/模板/操作时拒绝。P07提供唯一固定DOCX template ref。P05 Requirement Owner projection目前白名单字段为title、statement、rationale、domain_name、priority、risk、classification、acceptance_criteria。
- Plugin OperationCapability port要求enabled=true且trusted=true；当前无生产operation Registry/启用和正式trust事实，P04/CR-OUT-004已记录。Policy允许word.generate只能满足其中一条允许关系，绝不替代可信operation事实。
- 决定：P09实现一条只读内置、固定ref策略：DOCX + P07固定template + REQUIREMENT_VERSION + APPROVED；字段只开放title/statement/acceptance_criteria，最大4个来源、Context 8192字节；仅把word.generate作为受策略允许的操作标签。未知ref/目录异常fail closed。
- 由于无Policy Root/API，采用内置目录不改冻结Data Model/Schema/API，不加Migration，不支持用户编辑；不接生产Resolver、不触发插件、不生成文件或外发数据。新增策略版本才能扩大能力。
- CR-OUT-007已记录P09编码边界、风险、回滚及A17托管验证计划。P08结论PASS_SCOPE_LIMITED；P09只实现内置策略metadata。