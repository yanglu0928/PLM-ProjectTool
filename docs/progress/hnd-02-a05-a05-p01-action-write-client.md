# HND-02-A05-A05-P01：Action 七写前端客户端

日期：2026-10-05。结论：`HND_02_A05_A05_P01_ACTION_WRITE_CLIENT_PASS`。下一项：`HND-02-A05-A05-P02` Action 写操作工作台。

## 完成范围

- `SessionClient` 新增 Action CREATE、PATCH 与五个生命周期命令的同源传输；CSRF 继续只由会话 Owner 注入，调用方不能读取或替换。
- CREATE/START/SUBMIT/VERIFY/CLOSE/CANCEL 保留调用方提供的原始幂等键；PATCH 和生命周期命令保留原始强 ETag。传输失败不自动重试、不旋转 Key、不猜测结果。
- 新增严格七写客户端，发网前校验来源二选一、人工输入字段规格、UUID、UTC/带时区时间、文档/Evidence 唯一性、理由、Key 与 ETag。
- 成功回执重验 Project/Action 身份、状态、ETag 递增、Location、响应字段与请求绑定；所有回执均显式标记 `is_current_state_proof: false`，界面必须重新 GET 后才能声称当前事实。
- SUBMITTED、VERIFIED、CLOSED 保持三种独立结果；关闭缺真实 Resolution Owner 时继续投影 `HANDOVER_ACTION_RESOLUTION_REQUIRED`，未在前端绕过 CR-HND-008。

## 验证

- 专项：`handoverActionWriteClient.spec.ts` 20 项通过，覆盖七写、CSRF/If-Match/Idempotency-Key、输入失败关闭、安全错误映射、回执漂移与网络不确定性。
- 前端全量：75 个测试文件、1335 项测试全部通过。
- TypeScript/Vue 类型检查通过；Vite 160 模块生产构建通过。
- 主 JavaScript 为 540.63 kB（gzip 135.80 kB），超过 500 kB 的既有拆包警告继续作为发行性能项，不影响本项合同验收。

## 兼容、升级与回滚

无 Schema、Migration、后端 API、依赖、配置、Secret、网络或外发变化；只新增前端传输与未接线写客户端。删除新增客户端和 `SessionClient` 三个 Action 传输入口即可回滚，数据库历史不变。

P02 负责把能力接入工作台并依据当前会话角色与待办状态显示操作；真实浏览器闭环留 A06。首次回执不得替代 GET 当前事实。
