# CR-OUT-018：OutputRequest 列表前端只读接入

- 日期：2026-11-04
- 状态：编码前检查 PASS_WITH_LIMITATION；实施已由持续授权覆盖
- 来源：CR-OUT-017/P21冻结列表HTTP、API-03 OUTPUT_REQUEST_LIST、CR-EXEC-002 Windows 11 Pilot纵向链
- 基线：冻结 API Contract V1；只消费现有GET列表，不增加服务端接口、Schema或Migration

## 单一目标与方案

在 Vue 项目空间加入 OutputRequest 只读列表入口、分页 client 与页面，调用 /api/v1/projects/{project_id}/output-requests。UI 按 SessionView 隐藏 CustomerMember 和无项目权限入口，但服务端仍是最终授权来源。结果严格解析并只投影请求ID、类型、状态、请求/完成时间；不展示上下文指纹、快照引用、插件操作或正文。维护 cursor 加载更多、刷新、空态、Session/License/404/系统异常提示；项目切换/卸载时丢弃过期响应。默认产品路由对应 API 当前只在 Windows include_secret_read 组合存在。

## 编码前检查

- 前置任务：P21 PASS_SCOPE_LIMITED，专用Output cursor key与分页后端HTTP已在run 41846611865 PostgreSQL 18.6验收；API 只读、默认服务端未挂载。
- 模块：Vue Output API client、Output list view、Router、ProjectDetail navigation；消费现有 SessionClient 和浏览器 same-origin fetch。
- 权限呈现：只对当前项目成员列表入口可见；CustomerMember被拒于按钮级提示/隐藏，但绝不把客户端SessionView当安全边界；服务端 OUTPUT_REQUEST_LIST 仍授权PM/IM/CM并跨项目404。
- 分页：page_size固定50；校验响应字段、project_id、UUID、时间、state、分页游标与页间DESC顺序，拒绝重复cursor/重复请求ID；不渲染服务器未允许的额外内容。
- 验收：client解析/错误/分页合同测试；view角色/空态/分页/项目切换用例；Vue全量测试/typecheck/build；GitHub hosted workflow，并沿用PG18/A17/A34/A35/A50。所有运行仅在GitHub hosted runner D盘临时目录。
- 风险限制：仅新增只读UI，不创建请求、不提供撤销/重试、不代表真实插件生成文件；Pilot/Release与真实信任状态不变。


## 首次云端验收偏差与修复前记录

- 证据：GitHub hosted run [41857700593](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41857700593)，前端测试 job 失败；2,079/2,080 项测试通过，后端与其它云端工作仍在执行。
- 偏差 1：`OutputRequestListView.spec.ts` 中对象字面量断言类型跨行写法被 Vite/OXC 解析器拒绝（第 96 行），导致该测试套件无法加载。修复：调整为解析器接受的 TypeScript 断言格式，并由同一 GitHub hosted workflow 重跑。
- 偏差 2：`ProjectDetailView.spec.ts` 的直接 URL 用例使用没有授权项目的合成 Session，却断言应只对项目经理/实施成员/客户经理显示的入口。修复：将该用例改用合成项目经理 Session；另补充无权限角色不显示入口的断言，服务端授权仍为最终边界。
- 影响与风险：均为前端测试代码/入口呈现的验收偏差；未修改API、数据库、持久化数据或安全边界，不影响P21已通过结果。修复后要求全量前端测试、类型检查、生产构建及完整 hosted workflow 通过；失败则继续记录并修正。
- 限制：本次只记录hosted证据，不在开发者本机或C盘运行项目代码/测试；不据此宣称Pilot、Gate或Release通过。

- 第二轮云端验收偏差：修复后 run 41858761106 前端 2,083/2,084 测试通过；密码修改状态用例传入了同时含项目授权的合成 Session，`SessionClient` 在页面加载前按会话规则拒绝该不一致状态。修复：将密码修改用例改为合法的受限 Session（`password_change_required=true` 且无授权项目），继续验证视图拒绝行为；不改生产鉴权逻辑。风险与验收边界不变，必须由后续 hosted 全量回归确认。


## 最终状态复核（2026-11-05）

- P22 代码及前端测试已修正；最新 hosted run [41859511797](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41859511797) 的前端测试/typecheck/build、后端全量测试/wheel、PG18/pgvector、基础运行时、父包装配、clean extraction、A35、A17 与 A34 的全部步骤均返回 success；2,084/2,084 前端测试通过，13 个 job 中 11 个 job 已 completed/success。
- GitHub API 截至本记录时仍将 A17 与 A34 两个 Windows job 和整体 run 标为 in_progress，虽然两个 job 的所有步骤（含 Complete job）均为 success，且对应 bounded evidence artifacts 已上传。没有最终 aggregate conclusion，因此P22仅记为“实现与步骤级验证成功、汇总待终结”，不将完整WBS/Gate/Pilot/Release报为通过。
- 为遵循“客观阻塞转向独立任务”，下一项转入已批准Output Create契约的前端入口编码前检查；P23不修改A17/A34流程或依赖其最终状态。
