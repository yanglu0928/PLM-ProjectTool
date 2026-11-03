# OUT-01-A01-P06：Output文件模板固定版本Registry编码前核查

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED（完成固定基线/Owner核查；未编码）
- WBS：OUT-01-A01-P06
- 依据：CR-OUT-004/005、冻结DM-04/API-03及P05 PASS_SCOPE_LIMITED结果

## 问题

P04确认当前没有Output文件模板Registry；Prototype模板不是Output模板。P05已经提供经Requirement Owner授权的固定版本Source，但Output Resolver仍需可信的、不可变的模板版本才能建立内容格式约束。任何缺失或从Prototype数据推导出来的模板定义都必须保持失败关闭。

## 编码前检查

- 对照冻结架构、数据模型、DB Schema V1与API Contract，确认Output Template允许的Owner、字段、版本语义和可迁移边界；若必须修订冻结Schema，先建立Change Request并保留原冻结基线。
- 盘点Prototype模板数据模型/ORM/migration/权限及固定版本能力，证明其与Output文件模板在输入、格式、审核与Artifact语义上的兼容或不兼容，不跨模块直接查询ORM。
- 核实Output模块现有registry port、类型校验和当前实际挂载点；确定最小持久化Owner port及构造根接线边界。
- 盘点Output请求引用template version的冻结字段/索引/外键策略，标注FK是否可增加及其对既有记录/部署Migration的影响。
- 明确up/down migration、有数据/空库升级、并发/版本不可变性、授权、Review/发布状态、禁用/软删除语义和失败关闭条件。
- 若编码需要schema或migration，必须在本WBS记录CR、迁移/回滚与云端验证计划；遵循项目批准的持续授权实施，不请求普通WBS或Gate交界的重复批准。

## 验收与风险

盘点阶段不改代码或数据库，不新增模板、不伪造生产模板、不修改API。通过条件是选择一个有冻结契约依据且单一可验证的下一实现WBS，列明schema/API边界、信任来源、授权和迁移步骤；否则记录客观阻塞并转向其他不依赖模板的纵向链任务。全部证据通过GitHub托管runner/静态源码盘点获取，不在用户本机或C盘运行代码。

## 下一步

完成上列文件比对后，生成CR-OUT-006并登记单项模板Registry实现计划；若发现冻结Schema缺少必需持久字段，则CR先说明兼容方案、风险、升级/回滚和验证，不静默改写基线。


## 源码与冻结基线盘点结果（2026-11-04）

- 冻结Data Model V1将Output定义为2个Aggregate Root：OutputRequest、OutputArtifact；冻结DB Schema V1只映射Output请求与Artifact，没有OutputTemplate root/table。API-03仅在OutputRequest Create引用固定template_version_ref，并没有模板管理CRUD。
- Prototype Owner虽有PrototypeTemplate/Version，但其版本内容是不可执行的layout_contract/component_contract及原型artifact引用，服务于Prototype页面布局与组件/终端适用范围；它不定义Word/PPT/Flow输出格式与文档生成操作。跨模块复用会混淆边界，禁止直接读其ORM。
- 当前Output Owner仅有请求/ContextSnapshot持久化；Resolver定义OutputTemplateVersion DTO/Registry Port，缺真实Registry。新增可配置数据库模板root将偏离冻结65-root Data Model/Schema，还会增加Migration及管理API范围。
- 决定：P07实现受版本控制的内置OutputTemplate Registry，作为Output Owner的只读受控包内目录映射到Resolver既有DTO；不增加Aggregate Root、客户DB表、公开管理CRUD或项目自定义模板能力。固定模板版本ID绑定到受控代码/资源版本；未知ID与格式不匹配失败关闭。若后续必须支持管理员/项目自定义Output模板，再单独走Data Model/Schema Change Request。
- 已记录CR-OUT-006作为P07编码前批准记录；不改API/Schema/Migration，不读客户数据，不改变Plugin信任/启用状态。真实Output Create仍因Policy/operation和render/artifact链未齐全而失败关闭。
- P06结论PASS_SCOPE_LIMITED；下一项P07只实现内置Template Registry与契约测试，不执行插件、不生成客户文档。