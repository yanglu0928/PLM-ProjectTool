# SOL-06-A09-P06-P01：前端专项创建命令

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：冻结 API-04 SOL_SPEC_CREATE → A09-P03 Owner/P04 HTTP/P05 Windows → 本项。Phase 2。
- 编码前检查：受控 SessionClient、Origin/CSRF/Key 传输和后端 201 DRAFT 合同已具备；仅新增受控 POST 路径与独立客户端，页面/路由另项。不在浏览器裁决来源资格或人工确认。
- Changed：只让项目 Manager/ImplementationMember 提交包含类型载荷、至少一条固定 Requirement/Section、去重 Evidence、空 Artifact 的草案；SessionClient 私有 CSRF 发送，不向业务组件暴露 Token。严格核对 201 Trace/Location/项目/首次版本/载荷/引用/计数/指纹/Review 空值。网络断线、未知响应或矛盾回执保持不确定，让页面使用原 Key/原正文复核，不自动换号。
- Verification：定向 4 项，前端全量 135 文件/1764 项、typecheck/生产 build 通过。未接页面，未执行浏览器点击；P05 已单独证明真实 Win11/PG HTTP 链。
- 回滚/风险：移除未接页面客户端/Session 桥接即可回退，无服务端/数据变化。OutputArtifact、Trace/Spec、章节 ready_for_review、正式信任、Gate3/Pilot/Release 仍待。
- 2026-10-12 后续核对：P06-P02 编码前发现前端两处类型别名误写，与服务端 A06 `_VALIDATORS` 不一致；已将流程/权限类型改为 `PROCESS_MODEL`/`PERMISSION_DESIGN`，新增四类名称与旧别名负例，定向 5 项通过。页面接线前修复，不追写服务端冻结类型或既有历史。
