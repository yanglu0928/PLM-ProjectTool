# OUT-01-A01-P36：OutputArtifact 固定引用读取接口编码前检查

- 日期：2026-11-06
- 结论：PASS_WITH_LIMITATION（可实现，无Schema/API既有响应变化）
- CR：CR-OUT-032
- 前置：P35 PASS_WITH_LIMITATION；P34A/P34B PASS_SCOPE_LIMITED。

## 编码前检查

- 当前 Phase：Phase 2 Platform Core。
- 当前 WBS：OUT-01-A01-P36。
- 输入基线：OUT-02冻结Artifact、OUTPUT_REQUEST_GET/LIST、Project read authorization、DocumentVersion及Document下载不变量；CR-OUT-028/031/032。
- 前置任务：P34A生成DocumentVersion，P34B发布Storage，P33完成OutputRequest/Artifact成功事务；P35检出用户检索缺口。
- 涉及模块：output application/infrastructure/API；Windows output read composition；后端单元与父包PG18 verifier。
- 涉及实体：只读使用OutputRequestRow、OutputArtifactRow、DocumentRow、DocumentVersionRow、FileObjectRow；无实体/Migration。
- 涉及 API：新增 opt-in GET /api/v1/projects/{project_id}/output-requests/{output_request_id}/artifact；既有 GET/LIST 不变；返回Artifact ID、Document ID/Version ID、媒体类型、Hash/大小与受控内容URL。
- 涉及权限：重用会话、可信来源/CSRF、License与PROJECT读取权限；ProjectId和RequestId双条件查询；仅SUCCEEDED请求+唯一AVAILABLE Artifact+AVAILABLE Document/Version/FileObject可返回；缺失、跨项目、非可用、关系不一致统一404或系统安全错误；不提供Storage locator。
- 验收标准：应用层授权、无Artifact/非AVAILABLE/错误Project拒绝；HTTP Session/CSRF/License/字段封闭；PG18真实查询确认有效引用绑定、无效或污染数据不泄露；后端定向/全量/wheel与现有前端/build、父包验证。
- 风险：OutputRequest已完成但Artifact不可用时不可返回；文档下载URL若指向未装配路径会造成假可用。响应URL只针对冻结Document内容路由，Route存在不代表默认应用已组装。
- 回滚：移除新service/repository/router及Windows opt-in composition即可；无数据变更，已发布内容不删。
- 决策：将Endpoint独立于冻结详情，组合到现有Windows Output read opt-in router；不修改Storage/Output完成Owner，不挂载到默认login-only应用，不推断Pilot或正式服务已可下载。
- 验证计划：GitHub Actions Windows Server 2025 D盘临时空间+隔离PG18纯合成数据；加入PG18 verifier断言与各层回归，成功摘要必须为局部PASS；P25诊断按既定记录暂停。

## 参考文件检查

- OutputRequestReadService已提供项目Session、License及项目成员读取授权模式，可沿用。
- OutputArtifact冻结行同时绑定请求、项目、Document/DocumentVersion/FileObject身份与内容Hash/size/MIME。
- Document下载服务会对固定版本再次授权、比较前后来源快照，并从Storage对Hash与大小进行验证。
- 现有输出详情合同不可增字段；本项使用独立GET route。
- 生产Windows组合仅在受保护Platform模式里设置Output read与Document download routers；正式trust缺失不改变本项接口实现，但限制可用环境。

## P36范围

实现唯一的OutputRequest→AVAILABLE OutputArtifact→固定DocumentVersion安全投影及opt-in HTTP composition；不实现前端交互（拆为后续小项），不改既有Output API/Schema/默认组装。