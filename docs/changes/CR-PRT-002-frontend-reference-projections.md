# CR-PRT-002：Prototype 前端稳定引用与制品定位投影

日期：2026-10-08。状态：依据 `CR-EXEC-001` 持续授权批准实施。Gate 2 原冻结提交 `64cdf09`、
26 个 Prototype Operation、路径、请求、角色和错误语义均保持不变。

## 发现的偏差

`PRT_LINK_CREATE/PRT_LINK_SUPERSEDE` 要求 Coverage 按固定 RequirementVersion 的
AcceptanceCriterion 稳定引用完整分区，但当前 Requirement Version GET 只返回验收条件序号和五项正文，
没有返回数据库中已经存在的 `acceptance_criterion_id`。前端因此只能要求用户手工粘贴隐藏 UUID，或错误地
用序号/正文推导身份；两种做法都不能安全创建覆盖关系。

PrototypeTemplate/PrototypeVersion 的 ArtifactRef 当前只返回 `artifact_kind + target_id`。实际可用制品仅为
`DOCUMENT_VERSION`，其中 `target_id` 是 DocumentVersion ID；现有文档详情和固定正文 URL 还需要 Document ID。
前端无法在不扫描所有文档及历史版本的情况下定位固定原文，也不能把数据库或文件路径当定位信息。

以上是冻结合同落实到可操作 UI 后暴露的响应投影缺口，不是新增业务能力。API-04 已明确“响应可新增可选字段，
请求未知字段默认拒绝”，故采用兼容响应增量，不改写原冻结文件。

## 选择

- Requirement Version 详情中每项 `acceptance_criteria[]` 增加只读稳定业务引用
  `acceptance_criterion_ref`。它来自既有 AcceptanceCriterion 身份，不是内部 FK、序号哈希或客户端生成值。
- Prototype Template/Version 响应中的 `DOCUMENT_VERSION` ArtifactRef 增加只读 `document_id`，与
  `target_id`（DocumentVersion ID）共同形成受权业务定位；不得返回绝对路径、Storage Locator 或正文。
- 写请求仍只接受冻结字段，服务端严格拒绝客户端提交上述只读投影。既有响应字段、路径、权限、License、
  Session、CSRF、ETag、幂等和错误投影不变。
- 前端以服务端返回的引用构造选择器和固定文档链接；不显示要求用户维护 UUID，不把 AI 建议、模板内容或
  Artifact 正文自动填成正式事实。`OUTPUT_ARTIFACT` 在正式读取/定位 Owner 存在前继续明确显示不可定位，
  不猜测 URL。

## 实施、验证与回滚

1. `PRT-01-A10-A02` 先实现两个响应投影及后端/合同/真实 PostgreSQL 验证。
2. 后续 Prototype 严格客户端同时兼容旧响应：缺少新投影时只读展示可用，但覆盖写入/原文定位按钮失败关闭并
   给出可操作提示；不会降级为手填 UUID。
3. 再实施结构化页面、人工维护提示、未知结果恢复和真实 Edge 闭环。

无 Schema/Migration、依赖、Secret、客户数据外发或权限变化。应用回滚可移除可选响应字段和前端相关操作；
既有 Prototype、Requirement、Document、Review、Link、Trace、Audit 历史不修改。验证至少覆盖投影身份一致、
跨项目不可见、写入仍拒绝只读字段、严格解析兼容、完整后端/前端回归和 Windows 11/PostgreSQL 18.6。
Windows Server 2025 另行实机验证，Debian 13 依用户指令跳过。

## A02 实施记录（2026-10-08）

已在既有GET投影增加可选`acceptance_criterion_ref/document_id`，写请求仍严格拒绝只读字段；Document ID由
当前Document Owner按scope/project重新证明，证明缺失时不猜测定位。无Schema/Migration。Windows 11/
PostgreSQL 18.6真实三库、后端3211/3、前端1533、typecheck/build及wheel1229项/
`794c7dc4…273152`通过；进入A03严格只读客户端。

## A03 实施记录（2026-10-08）

五族严格只读客户端已覆盖冻结9项GET，兼容旧Artifact响应并把缺失`document_id`归一为不可操作状态；严格
校验父级、scope、顺序、身份唯一、五类cursor、强ETag、安全JSON合同及公开错误映射，不扫描或猜测定位。
定向30项、前端全量1563项、typecheck和production build通过；无后端API、Schema、依赖或权限变化，进入A04。

## A04 实施记录（2026-10-08）

Link写客户端只接受A02投影得到的稳定AcceptanceCriterion引用；Artifact写入仍严格只接受冻结的kind/version ID，
拒绝`document_id`回写。17项写操作保持原路径/请求/权限；未知结果不猜测、不自动重试，按原Key或GET对账。
前端全量1575项、typecheck/build通过，进入A05页面接入。
