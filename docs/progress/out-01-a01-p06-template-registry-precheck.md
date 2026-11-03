# OUT-01-A01-P06：Output文件模板固定版本Registry编码前核查

- 日期：2026-11-04
- 状态：PRECHECK_IN_PROGRESS（未完成证据盘点；未开始编码）
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
