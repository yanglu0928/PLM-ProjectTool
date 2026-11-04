# OUT-01-A01-P25 编码前检查：真实 Create HTTP + hosted Edge 失败关闭闭环

- 日期：2026-11-05
- 结果：PASS_WITH_LIMITATION，可进入同一WBS实现
- Change Request：CR-OUT-021
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P25

## 单一目标

在GitHub hosted Windows Server 2025 runner上，将同run前端production build、Edge浏览器和真实显式Windows Output Create HTTP组合接通；使用一次性合成Session、合成Project/Requirement、临时PostgreSQL 18及空Publisher信任源，验证真实后端的失败关闭错误能由UI安全显示，并确认OutputRequest/Job/Outbox/Audit/Idempotency相关持久计数没有变化。

本项只验“真实HTTP失败关闭如何经浏览器到达用户且无写入”。真实Publisher key和插件Worker缺失时，不允许人为配置可信测试key或伪造成功。

## 编码前检查与输入依据

- P19/CR-OUT-015已将冻结Create route接入显式Windows write composition；PG18合成HTTP验证ProjectManager/ImplementationMember在Publisher manifest为空时拒绝且无持久写入，CustomerManager被拒绝，默认App不挂载Create route。
- P24/CR-OUT-020已在hosted Edge验证真实production build，但其API由浏览器harness模拟；两项证据尚未组成一个真实浏览器到真实后端失败关闭请求。
- apps/backend/src/plm_assistant/entrypoints/windows_output_create.py通过包内signer resolver读取信任；默认候选信任manifest为空，API必须保持拒绝。HTTP合同已有SYSTEM_UNAVAILABLE/VALIDATION_FAILED错误映射；客户端只展示用户安全提示，不读内部上下文。
- P19验证器具备临时PG18建库、合成用户/项目/成员、Output相关表快照能力；P24 Node harness具备Windows Edge/D盘工作区与production build加载能力。实现边界为新增P25专用hosted桥接脚本与job，不改API/Schema/Migration/License/信任源/默认挂载。

## 验收计划

1. 由P25专用Python harness在GitHub hosted Windows runner D盘临时目录创建隔离PostgreSQL库，应用head migrations并写入合成项目成员；用真实create_windows_output_request_create_router创建HTTP app，publisher信任保持为空。
2. 同run下载的前端production build由Edge打开。登录/Requirement读取使用合成本地fixture，Output Create POST只经loopback转发到上述真实API；完整转发浏览器Origin、Cookie、CSRF、Idempotency与精确请求体。
3. 断言真实API返回合同允许的安全拒绝；UI显示对应通用提示、不显示202回执、500ms内无自动二次POST；受限DB快照中OutputRequest/Job/Outbox/Audit/Idempotency表计数与请求前完全一致；默认app仍无Create路由。
4. PG18 PGVector、前后端全量、wheel、父包、A17/A34/A35/A50及P25 Edge执行同一Hosted全链；记录artifact与去敏summary。
5. Secret检查只针对变更；检查脚本没有密钥/客户正文输出，Runner temp根路径必须D:。不在本机/C盘运行代码、安装依赖或测试。

## 风险、回滚与范围限制

- 如果真实路由返回202或数据库出现写入，验收必须失败并调查；不得将其改造成通过。P19空manifest基线须保持不可信。
- Node到Python API只使用localhost回环，浏览器仍只访问同源harness；使用唯一临时数据库名且finally清理。清理失败须在日志标为失败并保留runner托管临时区的处置证据。
- 失败关闭映射可能与UI安全提示不匹配；最小调整限于专用客户端错误映射/显示，不放宽服务端信任。
- 回滚：删除P25 Edge job、loopback桥接和隔离PG server/harness；如有UI安全映射改动则恢复原映射。无数据迁移、生产凭据或真实文件。
- 结论只能是PASS_SCOPE_LIMITED；不代表真实Publisher信任、插件执行、DOCX生成、Windows 11实机、Gate、Pilot或Release。

## 实施前Secret检查

本任务只增加固定合成身份/令牌、临时PG fixture和本机loopback地址；禁止使用任何账户/API/Publisher密钥。待编码前确认远端head且检查diff无Secret后开始。