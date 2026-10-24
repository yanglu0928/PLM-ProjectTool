# AUD-03-A07-P01：审计导出可选提交POST

2026-09-27/Phase2，编码前输入51e4faa、既有实际SubmitService/幂等Receipt/Audit-Job-Outbox同事务与已挂载Jobs GET，冻结API-02 AUDIT_EXPORT。涉及Audit API/Application调用，JOB-01仅受理引用，不在HTTP请求执行捕获/渲染/OCR/文件I/O。

单WBS：原项目/admin audit-exports POST可选Router，默认/当前Windows工厂不自动写挂载。Role原PM或Admin，S/L/C/I/A由可信Origin/Host、严格Cookie/CSRF/Key、Session预验证及Service同事务重验；Client scope/project/request actor不能指定。body<=8192 UTF8 JSON对象、拒绝重复key/未知字段/非标准常数。必填purpose/start_at/end_at，白名单action/outcome/actor_id(仅查询过滤)/target_object_type/target_object_id/trace_id(仅过滤)；明确aware RFC3339、UTC归一、31天上限/目的限制沿原Spec。无新Schema/权限/依赖，原冻结不改。

响应202固定首次受理JobRef（job_id/state=PENDING/status_url）加export_id，重放终态仍返回原受理语义，不复活Job；status_url GET为当前状态权威。Location=任务URL，不含Outbox/Audit/路径/Lease/payload。未知source/store等503脱敏；scope/purpose422、key内容冲突409、跨项目404、Session/CSRF/许可拒绝。Scope错误增量正式注册安全AUDIT_EXPORT_SCOPE_INVALID（API-02已有冻结错误）。

验收：Unit/HTTP入参/安全/固定响应绑定、实际PG两Scope202/重放六表无写/冲突/权限撤销/失败回滚、202 status_url可查询、真正Worker发布后重放不复活。不把同事务Mock当数据库证据。回滚撤可选Router和安全码注册保原写Service与历史，后Windows写装配单独验；正式信任/其他Owner/列表/取消/质量/UAT/完整包/Gate仍待。

实施/Files：Audit api/submit_export.py严格流式JSON/Spec/当前Session+原Service/安全202；entrypoints/api.py新增可选submit Router参数，platform/errors.py注册冻结scope错误；tests/contract/test_audit_export_submit_api.py与validation/aud-03-a07-p01-http/verify.py及Contract/进度/状态/决策/版本。Migration/依赖/角色无变化，默认及当前Windows装配POST仍关闭。

Tests：5新Contract、1155后端无失败/2既有权限跳过，固定响应/原绑定、默认404、浏览器Headers、大小/重复key/NaN/未知字段/不规范UUID/日期范围目的、Session/Service错误脱敏/错返回binding拒绝。真实Windows11/Python3.13/PG18+原SessionService/实际Cookie-CSRF/PM/Admin/原幂等提交：双Scope202与可查询PENDING，重复202原refs十表不写，改内容409、未知Session401/CSRF/Origin/License403、跨项目/撤PM/非Admin404。原Audit实际append后抛故障，十表（Root/Acceptance/Job/Outbox/Audit/Receipt/Lease/Attempt/Result/File）完全回滚；原真实领取/捕获/渲染/发布后status_url SUCCEEDED v2，终态重放保原202/PENDING受理快照而不改SUCCEEDED/单Attempt。原发布回归通过，License明确合成，非Windows正式装配或浏览器证明。

Result：可选HTTP已验范围PASS；不是完整任务模块/正式运行材料/监听服务器/前端/20并发/性能/UAT/三平台/安装包/Gate通过。本轮无测试失败；下一AUD-03-A07-P02仅Windows写模式装配，同原Service依赖与信任门禁，--platform只读及默认/login仍关闭提交。停止线/外发授权边界不变。

开发wheel通过：644844 bytes/SHA256 `f134dcc4fae6d3418b23421e0f4e2463e6a0c5b4555edd471daea7daa917fcc5`，仅构建证据，非完整可用安装包。
