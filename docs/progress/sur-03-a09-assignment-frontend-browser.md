# SUR-03-A09：Assignment/Response 前端与 Windows 11 真实浏览器

日期：2026-10-07。结论：`SUR_03_A09_ASSIGNMENT_EDGE_BROWSER_PASS`。下一项：`SUR-04-A01` SurveyConclusion 运行时前置核查与 Change Request。

## 编码前检查

- 当前 Phase：Phase 2 Platform Core。
- 输入基线：Gate 2 冻结 API-04 七个 Assignment/Response Operation，CR-SUR-008，已通过的 SUR-03-A08 后端/组合。
- 前置：0108、Assignment/Response Owner、Round completeness/CLOSE、HTTP 与 Windows 生产组合均已客观通过。
- 范围：前端严格客户端、页面/路由、Session CSRF 写桥、Windows 11 Edge 验收、兼容偏差记录；不改 Schema、冻结 URL、角色或后端业务状态机。
- 验收：页面不要求用户手工填写 UUID；六种题型均有受控输入；支持自助/实施代录、Evidence、追加更正、SUBMIT/VALIDATE/RETURN；写后重读；未知结果保留原 key/body/ETag 且不自动重发；全量测试、typecheck、build 与真实 Edge/PG 链通过。
- 风险：原生 `fetch` receiver，严格响应形状，动态成员可见性，超时后重复写，以界面或 AI 建议冒充客户确认。

## Changed

- 新增严格 Assignment/Response 读写客户端：父资源/身份/响应字段/稳定排序/ETag/cursor 均失败关闭；五个写操作复用 SessionClient 的 CSRF、幂等键与 `If-Match`。
- 新增调研分配与答复工作台。Department、Member、Question 和 Evidence 均来自当前受权列表，常规操作不需手填内部 ID；六类答案控件、FACILITATED_RECORD、追加式更正、SUBMIT/VALIDATE/RETURN 均可见且按状态失败关闭。
- 页面明确提示 AI 建议/录入不是客户确认；所有成功写都重新 LIST/GET，不把首次回执冒充当前事实；超时时保留原操作上下文。
- 在Round工作台增加分配/答复入口，新增嵌套路由。
- 根据 DEC-20261007-954，EvidenceListClient 以无接收者的普通函数形式调用原生 `fetch`；真实验收组合显式供给一次性 Evidence cursor key，不绕过友好选择器。
- 根据 DEC-20261007-955，VALIDATE 严格客户端接受已有后端 Review receipt 的规范 `return_comment: null`；SUBMIT 回执仍不接受该额外字段，RETURN 仍要求精确意见。

## Files / Migration / API

- 主要文件：`surveyAssignmentClient.ts/.spec.ts`、`ProjectSurveyAssignmentView.vue/.spec.ts`、`sessionClient.ts`、`router.ts`、`ProjectSurveyRoundView.vue`、`evidenceListClient.ts/.spec.ts`。
- 验收：`validation/sur-03-a09-assignment-browser/`。
- Migration：无；Schema head 仍为 `20261006_0108`。
- API：不新增、删除或修改冻结 URL/JSON；仅消费 A08 已实现的七个 Operation 及既有 Project/Department/Member/Evidence 受权读取。

## Tests / Result

- 定向：Assignment API/View 与 Evidence transport `15 passed`；修正 Review receipt 后相关客户端 `12 passed`。
- 前端全量：`86 files / 1466 passed`。
- TypeScript：`vue-tsc` 与 Node tsconfig PASS。
- 生产构建：Vite `180 modules` PASS；主 JS `687.36 kB` / gzip `171.03 kB`，既有 >500 kB 分块警告仍作为发行性能偏差，不冒充已解决。
- Windows 11 / Edge / PostgreSQL 18.6：实际构建 Vue 经生产 FastAPI 同源访问，完成登录→Project→CREATE/OPEN Round→部门级Assignment→四题Response→SUBMIT→VALIDATE→CLOSE；四张截图视觉核对通过，页面无可见alert。
- 独立 SQL 终检：`1 CLOSED Round / 1 VALIDATED Assignment / 4 Response / 4 Answer`；Audit 和幂等回执各 `10`，操作分布与链路一致。隔离数据库、凭据、文件、服务进程与 Edge profile 均已清理。
- 结果：`PASS`。

## 偏差与已知问题

- 真实 Edge 先后暴露：Evidence原生 fetch receiver、验收fixture缺 Evidence cursor key、脚本错把合成问题文案写死、VALIDATE Review receipt 含 `return_comment:null`。均按服务端权威合同做最小兼容修正并使用全新隔离库重跑；未放宽权限、完整性或业务状态。
- 定义写 UI、SRV-05 Conclusion、Survey Workflow 资格、完整模拟项目、Gate 3/UAT、Windows Server 2025 发行复验和可用程序包仍未完成。Debian 13 实机按用户指令跳过，正式兼容目标不删除。
