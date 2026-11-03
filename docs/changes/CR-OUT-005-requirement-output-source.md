# CR-OUT-005：Requirement固定版本作为Output Source的Owner读取适配

- 日期：2026-11-04
- 状态：编码前批准（CR-EXEC-002持续授权范围内）
- WBS：OUT-01-A01-P05
- 来源：OUT-01-A01-P04源码盘点；冻结API-03/DM-04；现存RequirementVersion Owner与Project授权实现

## 问题与证据

Output的TrustedOutputContextResolver需要输入source_version_ref、ProjectId及actor；其Source引用只含固定版本UUID。Requirement现有读取表与Owner支持固定版本，但读取方法要求调用方同时提供RequirementId，无法直接、安全地解析Output给定的Source UUID。P04确认RequirementVersion包含ProjectId、不可变version id和version_state，且Project授权策略已有REQ_VERSION_GET。

## 决定与边界

- 新增Requirement Owner级内部读取Port：按给定ProjectId和精确RequirementVersionId读取固定版本，重新检查当前Actor的REQ_VERSION_GET授权；不存在、跨Project、授权失败或版本不一致时统一拒绝。禁止查找current/latest或由调用方猜RequirementId。
- 仅输出Requirement Owner DTO；由应用组合根映射为Output的FixedSourceVersion，避免Requirement模块依赖Output模块。Source kind固定为Requirement版本类型；review_state原样返回，由Output Policy决定是否允许，不自动把DRAFT/IN_REVIEW变成APPROVED。
- 输出字段按P05实现前置白名单控制，只提供需求标题/陈述/理由/域/优先级/风险/分类及经确认的验收准则；不携带文件正文、客户Secret或绝对路径。Output resolver随后按Policy允许字段再做投影，缺Policy时仍失败关闭。
- 不改冻结API/数据模型/Schema，不加migration，不建立模板、策略、插件启用或执行能力；不外发客户数据。

## 验收、风险及回滚

- 定向Owner单测与隔离PG18 smoke验证精确固定读取、Project隔离、现行成员授权、版本状态保真及失败关闭；后端全量/wheel、Secret扫描、Windows父包与A17/A34托管验证。
- 仅合成身份/内容，在GitHub hosted runner的临时目录和disposable PostgreSQL执行。不得在用户本机/C盘运行。
- 风险是Requirement字段内容可能含用户业务正文；该读接口仅在服务端形成Output所需的最小快照候选，不发送模型或外部服务。后续真实Output调用仍受Policy/API/License门控。
- 若定向或PG测试失败，保留历史读API行为，回退新增Owner端口/组合适配，不修改历史版本或数据；Output源Resolver保持fail closed。
