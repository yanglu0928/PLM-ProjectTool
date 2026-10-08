# PRT-01-A10-A01 Prototype 前端范围与安全交互前置核查

日期：2026-10-08
状态：`PRT_01_A10_A01_FRONTEND_PRECHECK_PASS`

```text
前置任务：PRT-01-A09-A09 PASS
涉及模块：Prototype/Requirement/Document 前端与只读 API 投影
涉及实体：Package、Prototype、TemplateVersion、PrototypeVersion、RequirementPrototypeLink、AcceptanceCriterion、DocumentVersion
涉及API：冻结26项Prototype Operation及既有Requirement Version GET；本项不改代码或开放新路由
涉及权限：前端角色提示只是操作引导，服务端仍逐请求重证Session/License/Project角色
验收标准：固定页面范围、人工维护提示、原文定位、AI建议边界、未知结果恢复及客观接口缺口
风险：手填隐藏UUID、扫描猜测文档、模板/AI输出冒充客户事实、网络未知结果重复写入
```

## 对账结论

- Windows生产组合已提供冻结26项Operation；A10可在既有入口上建设，不新增“生成并批准”快捷命令。
- Requirement详情已有可复用交互：先解释“需要维护什么”，只显示来源标识与摘要，用户明确点击后才定位
  固定业务记录/Evidence/DocumentVersion，不把原文批量复制到表格；AI任务明确标为建议。
- Prototype服务当前只接受可验证的`DOCUMENT_VERSION`制品。虽类型保留`OUTPUT_ARTIFACT`，现有Owner会
  失败关闭；页面不得把它描述为可用或构造猜测链接。
- 两个响应投影缺口会阻断友好且正确的写入/定位：Requirement读取缺AcceptanceCriterion稳定引用；
  ArtifactRef读取缺Document ID。已建立`CR-PRT-002`，按冻结API“响应可新增可选字段”规则兼容修复。

## 页面和操作范围

|页面/区域|读取|允许的受控操作|必须给用户的提示|
|---|---|---|---|
|原型列表|Prototype列表、状态、批准指针|创建Prototype；进入范围决定|原型为空不等于“不需要原型”|
|原型详情|Root、Package归属、版本、固定需求、制品、模板、Link|改名、归档、显式NOT_REQUIRED、创建/校验/送审版本|模板和AI结果仅是输入；批准只由Review完成|
|原型包|Package及当前成员|创建、改名、全量设置成员|全量设置会替换现有集合，不删除Prototype历史|
|模板|PROJECT及获准GLOBAL模板|PROJECT创建/修订；GLOBAL管理面仅管理员|GLOBAL模板没有客户事实；选择固定版本而非latest|
|覆盖关系|固定双端和Coverage|创建、撤销、替换|逐条选择验收条件；未覆盖项必须填写原因|
|制品定位|固定DocumentVersion引用|打开文档版本历史/受权固定原文|不返回磁盘路径；不可用时保留历史并明确失败|

页面不提供任意JSON编辑器作为主流程。Layout、Component、Interaction、Coverage等结构化合同使用分组字段、
枚举和逐项增删；技术ID由列表选择产生，仅在诊断信息中按需显示。Review提交继续复用合格评审人选择，不能
把“校验通过”写成“审批通过”。

## 并发、重试与恢复

- PATCH使用最后一次GET返回的强ETag；冲突后重新读取，不自动覆盖。
- 幂等写在首次点击时生成并保留同一key；超时或断网后先使用原key恢复首次结果。用户修改正文后才生成
  新key。无幂等控制的PATCH不自动重发。
- 页面卸载、切换项目、登出或权限撤销时，丢弃迟到响应并清除私有CSRF和待恢复写状态。
- 读投影缺少`acceptance_criterion_ref/document_id`时，保持安全只读，禁用相应Link写入或固定原文按钮，
  显示“服务端版本尚不支持此操作”；不降级到手填UUID或全库猜测。

## A10执行拆分

1. `PRT-01-A10-A02`：落实CR-PRT-002稳定引用/Document定位响应投影并验证。
2. `PRT-01-A10-A03`：五族严格只读客户端、类型、错误和游标边界。
3. `PRT-01-A10-A04`：受控写传输、ETag/幂等与未知结果恢复。
4. `PRT-01-A10-A05`：列表/详情/Package/Template/Version/Link结构化页面及人工维护提示。
5. `PRT-01-A10-A06`：Router/项目导航、权限即时撤销和完整前端回归。
6. `PRT-01-A10-A07`：Windows 11/真实Edge/PostgreSQL 18.6读写闭环。

本项只完成前置核查，不声称前端、Edge、Windows Server 2025、Gate 3或UAT已通过。
