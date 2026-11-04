# CR-OUT-019：基于已批准需求版本的 Output DOCX 请求入口

- 日期：2026-11-05
- 状态：编码前检查 PASS_WITH_LIMITATION；前端实现已提交，GitHub hosted 验收待完成
- 来源：CR-EXEC-002 Windows 11 Pilot 纵向链、冻结 API-03 OUTPUT_REQUEST_CREATE、CR-OUT-009/P12、CR-OUT-015/P19、CR-OUT-018/P22
- 基线：冻结 API Contract V1、现有 OutputRequest Owner；不改 API、Schema 或 Migration

## 单一目标与决定

在项目需求固定版本详情中，为当前已批准的 RequirementVersion 提供用户主动发起的内置 DOCX 请求入口。仅使用包内固定版本：template a1272ce0-01f0-5e6c-9706-000000000001、policy output.policy.requirement-docx.v1、operation word.generate；source_version_refs只包含用户当前选择且服务端复核为 APPROVED 的 RequirementVersion。用户继续在业务页面读取和核验来源，不复制来源正文到客户端请求。

客户端复用 SessionClient same-origin POST、CSRF、Idempotency-Key 与角色呈现；只允许 PROJECT_MANAGER/IMPLEMENTATION_MEMBER 发起。每次提交只创建一次性幂等操作；结果不确定时保留原 key，提示用户先查历史，不换key自动重试。服务器 Session、项目权限、License、版本状态、策略、插件安装/启用/签名信任仍为唯一最终判定。

## 限制与安全边界

- 请求只表示已提交/排队的 OutputRequest，不表示 DOCX 已生成、可下载或经过人工验收；不执行插件或渲染文件。
- P19证据显示包内受信任publisher keys为空；缺正式可信Publisher时，服务器必须失败关闭且不得产生 Request/Job/Outbox/Audit/receipt副作用。UI仅显示安全的不可用提示；不得绕过信任校验。
- 现有Create HTTP只在显式 Windows include_secret_write 组合可用，默认App仍不挂载；本WBS不改变默认挂载或密钥配置。
- 不显示Context正文、fingerprint、内部快照路径、插件操作结果或Secret；不调用AI/外部服务，不使用客户材料验证。

## 变更 / 风险 / 回滚

只改前端 SessionClient允许的固定POST路径、Output Create client/view 与Requirement固定版本详情入口及测试。无数据库迁移与服务端改动。主要风险是错误版本/幂等重试误导或客户端角色提示被误当安全边界；由精确payload、固定引用、服务端复核、保留原幂等key、错误状态与合成用例控制。回滚为移除入口/client和相关测试，保留冻结API与后台Owner。

## 验收计划

Output Create client合同/错误测试、Approved/非Approved版本与角色显示测试、幂等不确定结果提示、Requirement detail导航；GitHub hosted 全量前端与后端测试/typecheck/build、PG18及父包/A17/A34/A35/A50。所有程序/测试仅在GitHub hosted runner或非C盘沙箱执行；不使用本机C盘。

## 实施提交（2026-11-05）

已实现SessionClient固定POST路径、Output DOCX请求client与需求固定版本入口；UI只向当前已批准版本/PM或IM开放。幂等key在同一组件尝试中保留；提交状态不确定时禁止自动重试并提供历史核对入口。后端Owner仍复核Session/CSRF/Project/License/版本/插件签名信任。未改API、Schema、默认路由或密钥来源；没有执行插件或生成文件。本提交云端全量验收进行中，完成前不标记P23通过。
