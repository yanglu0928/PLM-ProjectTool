# AI-05-A02 前端 AI 严格只读客户端

日期：2026-10-03；状态：`AI_READ_CLIENT_PASS`；依据冻结 API-03、CR-AI-020、DEC-770～778及P07 Windows读取组合。下一项：`AI-05-A03` AI任务/建议只读工作台页面。

## 编码前检查

|字段|结论|
|---|---|
|当前Phase|Phase 2 Platform Core|
|当前WBS|`AI-05-A02`|
|输入基线|冻结`AI_TASK_LIST/GET/INVOCATION_LIST/SUGGESTION_GET`；P07真实HTTP响应；`gap-output.v1/v2`与Document locator合同|
|前置任务|AI-04-A07-P07 Windows11读取组合 PASS|
|涉及模块|仅前端`modules/ai/api`|
|涉及实体|AITask、AIInvocation、SuggestionPayload的只读DTO|
|涉及API|四条既有冻结GET；无新增或修改|
|涉及权限|完全由后端当前Session/License/Project/Document授权；客户端不推断或缓存权限|
|验收标准|同源GET/no-store；严格运行时校验；游标不解码；V1/V2定位/提示可验证；错误不泄露；超时单次中止|
|风险|接受服务端异常字段、错误绑定或任意URL会导致敏感信息进入UI；把建议当正式事实会破坏业务边界|

## 实现

新增`AIReadClient`，提供Task列表/详情、Invocation列表和Suggestion详情。所有输入ID、page size和cursor family在网络前校验；请求固定为同源GET、`credentials=same-origin`、`cache=no-store`、拒绝重定向、10秒有界超时且不自动重试。HTTP只映射状态匹配的401/403/404安全错误，其余统一为不可用，不透传服务端message。

客户端从响应白名单重建并冻结DTO：Task/Invocation绑定、时间顺序、状态、版本引用、分页去重及稳定倒序均需成立；详情ETag响应头必须与body一致。Suggestion固定`NOT_FORMAL_FACT`，只接受注册的`gap-output.v1@1`或`v2@2`；V1只能匹配`DOCUMENT`定位，V2的citation节点集合必须与Document Owner返回的`PARSED_NODE`集合完全一致。content URL必须精确绑定当前Project/Document/Version；locator按九类结构验证；`PENDING_CONFIRMATION`必须给出受控字段、维护提示、原因和至少一个必填项。未知外层字段被丢弃，canonical payload未知字段直接拒绝。

## 验收、兼容与回滚

定向29项通过；前端全量62个文件、1223项通过；`vue-tsc`与Node TypeScript检查通过；Vite生产构建131模块成功。构建产物：`index.html` SHA-256 `0f39d936de13699121669af59df18b1eb932b10eea18be3c28d6ebcd6214ea23`、JS `c09a4be07ec7de1ba68a8fa55d1fb267c4a7d2c781e3f6609ae739db31fe5e08`、CSS `bae9fe6c1c58c3bc6a4a0fffe96a7cc92f72a90a89bfc820f6c4e80f355f7a3f`。本项无后端、Migration、依赖、公开合同或数据外发变化，未重复运行后端回归。回滚删除客户端与测试即可，不影响后端历史。页面、取消/重试编排、外发授权交互、Accept/Reject目标Draft写闭环、真实浏览器/UAT/发行包仍待后续。
