# API Contract V1 增量：Prototype 稳定引用与Document定位投影

日期：2026-10-08。依据：`CR-PRT-002`。本增量不改写Gate 2冻结提交`64cdf09`，不增加Operation、路径、
请求、角色或错误码；适用API-04中既有Requirement Version GET、PrototypeTemplate LIST和PrototypeVersion
LIST/GET响应。

## 可选响应字段

|响应对象|新增字段|类型|语义|
|---|---|---|---|
|`RequirementVersion.acceptance_criteria[]`|`acceptance_criterion_ref`|UUID string|固定RequirementVersion内既有AcceptanceCriterion稳定业务引用|
|`PrototypeTemplate.artifact_refs[]`|`document_id`|UUID string|仅`artifact_kind=DOCUMENT_VERSION`且当前Document Owner证明可访问时返回的Document根ID|
|`PrototypeVersion.artifact_refs[]`|`document_id`|UUID string|仅`artifact_kind=DOCUMENT_VERSION`且当前项目Document Owner证明可访问时返回的Document根ID|

`target_id`继续表示DocumentVersion ID。前端只有同时取得`document_id + target_id`时，才可生成固定文档历史和
受权版本正文链接。字段缺失表示旧服务或当前不可定位，不表示制品不存在；客户端不得扫描全库、根据序号/正文
生成ID、猜测URL或显示绝对路径。

## 请求与兼容规则

- 三个字段均为只读投影。所有既有写请求继续严格按冻结字段集合校验，提交
  `acceptance_criterion_ref`或`document_id`返回`400 REQUEST_MALFORMED`。
- 旧客户端可忽略新增响应字段。新客户端兼容字段缺失并归一为不可操作状态；Coverage写入和固定原文定位
  必须在对应引用存在时开放。
- 响应不包含Storage Locator、磁盘路径、正文或内部表/列名；Session、License、项目隔离和防枚举不变。
- Requirement稳定引用来自已有Schema身份；Document ID在读取事务中重新调用Document Owner证明，不保存
  新的跨模块副本，不改变Artifact内容指纹。
