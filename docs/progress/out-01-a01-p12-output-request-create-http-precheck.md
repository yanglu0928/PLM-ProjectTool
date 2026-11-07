# OUT-01-A01-P12：OutputRequest Create HTTP 可选边界（编码前检查）

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED；hosted run 41780566043通过
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P12
- 依据：冻结 API-03 / API Contract V1，OutputRequest 内部 Owner（P01～P02）、Resolver/Policy/Template/Source/Plugin capability（P03～P11）
- 执行环境：GitHub hosted runner/沙箱；临时文件与数据库只在 runner 临时目录；不在用户本机运行项目程序

## 单一目标

为冻结契约 POST /api/v1/projects/{project_id}/output-requests 提供可注入、默认不挂载的 FastAPI router/HTTP adapter，调用现有 OutputRequest Owner 并返回 202 RequestRef + JobRef。该项只接一个 Create 操作，不实现 List/Get/Cancel/Regenerate/Artifact、输出执行或文件发布。

## 编码前核查

- 现有 OutputRequestService.create() 已负责 session/CSRF/Project角色授权、License、固定 source/template/policy/plugin capability、幂等、Owner事务、Job enqueue 和 Audit；HTTP 层不得复制或绕过这些规则。
- request body 只允许 output type、固定 template version ref、固定 source version refs、固定 policy ref 与 operation id；拒绝 current/latest、内部字段、额外正文和路径。
- 依据 API-03 使用 Idempotency-Key、trace envelope 和 CSRF/session控制，成功为 202；将 OutputRequestError 映射到冻结安全错误合同，不回传内部异常。
- router 由显式组合者注入且保持非默认挂载。当前正式publisher registry为空，产品组合返回 trusted=false，Resolver 应继续拒绝，不得以 HTTP 路由存在表示可生产生成。
- 测试仅合成 HTTP/合成数据库；覆盖权限/CSRF/License拒绝、无效请求、幂等重放、Resolver fail-closed及202投影。无客户数据外发、无外部AI、无文件生成、无Migration或API Contract修改。

## 风险、迁移与回滚

没有Schema/API Contract迁移。主要风险为 HTTP DTO过度接受字段或把服务内部错误泄露；使用严格字段白名单、稳定错误映射和最小202 projection控制。回滚只移除router与HTTP测试，内部Owner保持不变。

## 编码前结论

现有 Owner 及其依赖已具备单端点 HTTP 接入条件。按 CR-OUT-009 开始实现；正式服务默认不挂载，本轮 synthetic positive 只用于契约测试，不代表产品正式信任。
