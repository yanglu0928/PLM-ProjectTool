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
