# WFL-01-A07-P07-A06 Checklist 记录安全客户端

## 结论

`PASS` —— 前端已具备 Checklist 记录的单次安全传输与严格回执校验客户端，仅开放已有真实业务 Owner 的 `HANDOVER_BASELINE` / `HANDOVER_ISSUES` 与 `PASS` / `FAIL`。

本项未将写入 Workflow 页面。现有 Workflow/Handover 读取合同不返回服务端资格 Owner 判定的完整 Evidence 集；让用户手填或让前端猜测 UUID 会破坏服务端精确集合复验，也不符合既定的低人工负担交互。该缺口转入下一 WBS 的可追溯资格预览读边界。

## Changed

- `SessionClient` 新增 Checklist 专用 POST 传输：CSRF 仅由会话 Owner 注入，路径限制在两个 Handover Item，强 `If-Match`、幂等键和 2 MiB 请求上限失败关闭。
- 传输不自动重试；超时/网络错误后由调用方保留原 body、Key 和 ETag。`401` 立即清除本地写权证明。
- 新增 `WorkflowChecklistRecordClient`，校验 Workflow 当前处于 Handover，对 `PASS` 要求非空且唯一的 canonical Evidence UUID，`FAIL` 必须为空集，`WAIVED` 在无 ApprovedException Owner 时不开放。
- 成功回执对字段白名单、身份、版本、ETag、证据集、Review/Exception 引用和请求绑定逐项复验；返回值明确为不可变首次回执，不是当前状态证明。

## Files

- `apps/frontend/src/modules/auth/api/sessionClient.ts`
- `apps/frontend/src/modules/auth/api/sessionClient.spec.ts`
- `apps/frontend/src/modules/workflow/api/workflowChecklistRecordClient.ts`
- `apps/frontend/src/modules/workflow/api/workflowChecklistRecordClient.spec.ts`
- `docs/decisions/decision-log.md`
- `STATUS.md`
- `CHANGELOG.md`

## Migration / API

- Migration：无。
- 后端 API：无变更，消费 A04/A05 已实现的冻结 POST。
- 前端公开面：新增未接页面的安全客户端。

## Tests

- 前端全量：`76` 个测试文件、`1363` 项全部通过。
- `pnpm --dir apps/frontend typecheck`：PASS。
- `pnpm --dir apps/frontend build`：PASS，Vite 转换 `161` 个模块。
- 构建仍有既知主 JS `565.71 kB` 的 500 kB 拆包警告，未影响本项行为验收。

## Result / Known Issues / Next

- Result：`WFL_01_A07_P07_A06_FRONTEND_CLIENT_PASS`。
- Known Issues：无权威 Checklist 资格预览时，页面不能安全发起 PASS；页面成功后强制 GET 刷新、真实浏览器与性能尚未验收。
- Next：`WFL-01-A07-P07-A07` 登记并实现 Checklist 资格预览读边界，不更改冻结写 DTO，不暴露文档正文或内部路径。
